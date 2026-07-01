"""
storage/signal_db.py — SQLite database for signal history, dedup, CME gap tracking,
and lightweight performance feedback.

Using SQLite because it's zero-infrastructure, runs on 1GB VPS,
and persists perfectly across bot restarts.
"""
import sqlite3
import json
import datetime
from pathlib import Path
from loguru import logger
from config import DB_PATH, SIGNAL_DEDUP_HOURS


def _get_conn() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all tables on first run."""
    conn = _get_conn()
    c = conn.cursor()

    # Signal history — every fired signal
    c.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol      TEXT NOT NULL,
            direction   TEXT NOT NULL,  -- LONG, SHORT, NO_TRADE
            master_score REAL,
            strength    TEXT,
            pipeline_scores TEXT,       -- JSON
            context     TEXT,           -- JSON
            fired_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Signal outcome tracking — checked later by storage/performance_tracker.py
    c.execute("""
        CREATE TABLE IF NOT EXISTS signal_outcomes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id   INTEGER NOT NULL,
            horizon     TEXT NOT NULL,  -- 1h, 4h, 24h
            outcome_pct REAL,
            is_win      INTEGER,
            checked_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(signal_id, horizon)
        )
    """)

    # CME gap tracking
    c.execute("""
        CREATE TABLE IF NOT EXISTS cme_gaps (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            gap_price   REAL NOT NULL,
            gap_type    TEXT NOT NULL,   -- UP or DOWN
            gap_date    TIMESTAMP,
            filled      INTEGER DEFAULT 0,
            filled_at   TIMESTAMP
        )
    """)

    # Event cache — prevent re-processing same events
    c.execute("""
        CREATE TABLE IF NOT EXISTS event_cache (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id    TEXT UNIQUE,
            event_type  TEXT,
            payload     TEXT,  -- JSON
            cached_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Coin events calendar
    c.execute("""
        CREATE TABLE IF NOT EXISTS coin_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol      TEXT,
            event_type  TEXT,
            description TEXT,
            event_date  TIMESTAMP,
            impact_score REAL,
            processed   INTEGER DEFAULT 0
        )
    """)

    # Macro events
    c.execute("""
        CREATE TABLE IF NOT EXISTS macro_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name  TEXT,
            event_date  TIMESTAMP,
            actual      REAL,
            forecast    REAL,
            previous    REAL,
            impact      TEXT,   -- HIGH, MEDIUM, LOW
            processed   INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()
    logger.info("Database initialized")


# ═══════════════════════════════════════════
# SIGNAL DEDUP
# ═══════════════════════════════════════════

def was_signal_recently_fired(symbol: str, direction: str) -> bool:
    """
    Prevent spam: check if same direction signal was fired
    for this coin within SIGNAL_DEDUP_HOURS.
    """
    conn = _get_conn()
    c = conn.cursor()
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=SIGNAL_DEDUP_HOURS)
    c.execute("""
        SELECT COUNT(*) as cnt FROM signals
        WHERE symbol = ? AND direction = ? AND fired_at > ?
    """, (symbol, direction, cutoff))
    result = c.fetchone()
    conn.close()
    return result["cnt"] > 0


def save_signal(symbol: str, direction: str, master_score: float,
                strength: str, pipeline_scores: dict, context: dict):
    """Persist a fired signal to history."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO signals (symbol, direction, master_score, strength,
                             pipeline_scores, context)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        symbol, direction, master_score, strength,
        json.dumps(pipeline_scores),
        json.dumps(context),
    ))
    conn.commit()
    conn.close()


def get_recent_signals(hours: int = 24) -> list:
    conn = _get_conn()
    c = conn.cursor()
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=hours)
    c.execute("""
        SELECT * FROM signals WHERE fired_at > ? ORDER BY fired_at DESC
    """, (cutoff,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


# ═══════════════════════════════════════════
# SIGNAL OUTCOME TRACKING
# ═══════════════════════════════════════════

def get_outcome_candidates(hours_after: int, horizon: str) -> list:
    """Return fired signals old enough to check for a horizon and not already checked."""
    conn = _get_conn()
    c = conn.cursor()
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=hours_after)

    c.execute("""
        SELECT s.*
        FROM signals s
        LEFT JOIN signal_outcomes o
            ON o.signal_id = s.id AND o.horizon = ?
        WHERE s.fired_at <= ?
          AND o.id IS NULL
        ORDER BY s.fired_at ASC
    """, (horizon, cutoff))

    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def save_signal_outcome(signal_id: int, horizon: str, outcome_pct: float, is_win: bool):
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT OR IGNORE INTO signal_outcomes (signal_id, horizon, outcome_pct, is_win)
        VALUES (?, ?, ?, ?)
    """, (signal_id, horizon, outcome_pct, 1 if is_win else 0))
    conn.commit()
    conn.close()


def get_outcome_summary(days: int = 30) -> dict:
    conn = _get_conn()
    c = conn.cursor()
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    c.execute("""
        SELECT o.*
        FROM signal_outcomes o
        WHERE o.checked_at >= ?
    """, (cutoff,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    if not rows:
        return {"tracked": 0, "win_rate": 0.0, "avg_outcome_pct": 0.0}

    wins = sum(1 for r in rows if r.get("is_win"))
    avg = sum(float(r.get("outcome_pct") or 0) for r in rows) / len(rows)

    return {
        "tracked": len(rows),
        "win_rate": round((wins / len(rows)) * 100, 1),
        "avg_outcome_pct": round(avg, 3),
    }


# ═══════════════════════════════════════════
# CME GAPS
# ═══════════════════════════════════════════

def save_cme_gap(gap_price: float, gap_type: str, gap_date: datetime.datetime):
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT id FROM cme_gaps
        WHERE ABS(gap_price - ?) < 500 AND filled = 0
    """, (gap_price,))
    if c.fetchone():
        conn.close()
        return
    c.execute("""
        INSERT INTO cme_gaps (gap_price, gap_type, gap_date)
        VALUES (?, ?, ?)
    """, (gap_price, gap_type, gap_date))
    conn.commit()
    conn.close()
    logger.info(f"CME gap saved: {gap_type} at ${gap_price:,.0f}")


def get_open_cme_gaps() -> list:
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM cme_gaps WHERE filled = 0 ORDER BY gap_date DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def mark_cme_gap_filled(gap_id: int):
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""
        UPDATE cme_gaps SET filled = 1, filled_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (gap_id,))
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════
# EVENT CACHE
# ═══════════════════════════════════════════

def is_event_cached(event_id: str) -> bool:
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM event_cache WHERE event_id = ?", (event_id,))
    result = c.fetchone() is not None
    conn.close()
    return result


def cache_event(event_id: str, event_type: str, payload: dict):
    conn = _get_conn()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT OR IGNORE INTO event_cache (event_id, event_type, payload)
            VALUES (?, ?, ?)
        """, (event_id, event_type, json.dumps(payload)))
        conn.commit()
    except Exception as e:
        logger.error(f"Event cache error: {e}")
    finally:
        conn.close()


# ═══════════════════════════════════════════
# COIN EVENTS
# ═══════════════════════════════════════════

def save_coin_event(symbol: str, event_type: str, description: str,
                    event_date: datetime.datetime, impact_score: float):
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO coin_events (symbol, event_type, description, event_date, impact_score)
        VALUES (?, ?, ?, ?, ?)
    """, (symbol, event_type, description, event_date, impact_score))
    conn.commit()
    conn.close()


def get_upcoming_coin_events(symbol: str, days_ahead: int = 7) -> list:
    conn = _get_conn()
    c = conn.cursor()
    now = datetime.datetime.utcnow()
    cutoff = now + datetime.timedelta(days=days_ahead)
    c.execute("""
        SELECT * FROM coin_events
        WHERE symbol = ? AND event_date BETWEEN ? AND ?
        ORDER BY event_date ASC
    """, (symbol, now, cutoff))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows
