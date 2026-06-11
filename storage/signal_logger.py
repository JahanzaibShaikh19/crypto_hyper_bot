"""
storage/signal_logger.py — CSV signal log for backtesting analysis.

Every signal gets appended to a CSV so you can later
analyze which conditions actually predicted correctly.
"""
import csv
import datetime
from pathlib import Path
from loguru import logger


SIGNAL_CSV_PATH = "logs/signal_history.csv"

CSV_HEADERS = [
    "timestamp_utc", "symbol", "direction", "master_score", "strength",
    "ta_score", "correlation_score", "fa_score", "sentiment_score", "events_score",
    "pipelines_agreeing", "fear_greed", "funding_rate",
    "price_at_signal", "context_summary"
]


def log_signal_csv(
    symbol: str,
    direction: str,
    master_score: float,
    strength: str,
    pipeline_scores: dict,
    pipelines_agreeing: int,
    fear_greed: int,
    funding_rate: float,
    price: float,
    context_summary: str,
):
    """Append signal to CSV for later backtesting."""
    Path(SIGNAL_CSV_PATH).parent.mkdir(parents=True, exist_ok=True)

    file_exists = Path(SIGNAL_CSV_PATH).exists()

    try:
        with open(SIGNAL_CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            if not file_exists:
                writer.writeheader()

            writer.writerow({
                "timestamp_utc": datetime.datetime.utcnow().isoformat(),
                "symbol": symbol,
                "direction": direction,
                "master_score": round(master_score, 3),
                "strength": strength,
                "ta_score": pipeline_scores.get("ta", 0),
                "correlation_score": pipeline_scores.get("correlation", 0),
                "fa_score": pipeline_scores.get("fundamental", 0),
                "sentiment_score": pipeline_scores.get("sentiment", 0),
                "events_score": pipeline_scores.get("events", 0),
                "pipelines_agreeing": pipelines_agreeing,
                "fear_greed": fear_greed,
                "funding_rate": funding_rate,
                "price_at_signal": price,
                "context_summary": context_summary[:200],
            })
    except Exception as e:
        logger.error(f"CSV log error: {e}")
