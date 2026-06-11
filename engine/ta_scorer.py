"""
engine/ta_scorer.py — Technical Analysis Pipeline Scorer.

Combines all 5 TA layers into a single -10 to +10 score.
This is Pipeline 1, weighted at 35% of master score.

Layer weights:
  Layer 1 (HTF Trend):    35% — Pentoshi: structure is king
  Layer 2 (Momentum):     25% — Cobie: momentum = entry timing
  Layer 3 (Volume):       20% — Ansem: volume precedes moves
  Layer 4 (Derivatives):  10% — Hayes: derivatives never lie
  Layer 5 (Structure):    10% — Hsaka: max confluence
"""
import pandas as pd
from loguru import logger

from pipelines.technical.layer1_trend     import score_layer1
from pipelines.technical.layer2_momentum  import score_layer2
from pipelines.technical.layer3_volume    import score_layer3
from pipelines.technical.layer4_derivatives import score_layer4
from pipelines.technical.layer5_structure  import score_layer5


LAYER_WEIGHTS = {
    "layer1": 0.35,
    "layer2": 0.25,
    "layer3": 0.20,
    "layer4": 0.10,
    "layer5": 0.10,
}

# Each layer's natural range for normalization
LAYER_RANGES = {
    "layer1": (-2.5, 1.5),
    "layer2": (-1.5, 1.5),
    "layer3": (-1.0, 1.0),
    "layer4": (-1.0, 1.0),
    "layer5": (-1.0, 1.0),
}


def normalize_to_10(score: float, min_val: float, max_val: float) -> float:
    """Normalize any range to -10..+10."""
    if max_val == min_val:
        return 0.0
    # Center around 0, scale to [-10, +10]
    normalized = (score - (max_val + min_val) / 2) / ((max_val - min_val) / 2) * 10
    return round(max(-10.0, min(10.0, normalized)), 3)


def run_ta_pipeline(
    df_15m: pd.DataFrame,
    df_1h: pd.DataFrame,
    df_4h: pd.DataFrame,
    df_1d: pd.DataFrame,
    funding_data: dict,
    oi_data: dict,
    liq_data: dict,
    ticker_data: dict,
    btc_dom_data: dict,
    symbol: str,
) -> dict:
    """
    Run all 5 TA layers and return normalized pipeline score.

    Returns dict with:
      - score: -10 to +10
      - layers: individual layer results
      - summary: human-readable lines for Telegram
      - is_bullish: bool (score > 0)
    """
    # Run all layers
    l1 = score_layer1(df_4h, df_1d)
    l2 = score_layer2(df_1h, df_15m)
    l3 = score_layer3(df_4h, df_1h)
    l4 = score_layer4(funding_data, oi_data, liq_data, ticker_data)
    l5 = score_layer5(df_4h, btc_dom_data, symbol)

    scores = {
        "layer1": l1["score"],
        "layer2": l2["score"],
        "layer3": l3["score"],
        "layer4": l4["score"],
        "layer5": l5["score"],
    }

    # Weighted composite (all layers in their natural ranges)
    raw_composite = sum(scores[k] * LAYER_WEIGHTS[k] for k in scores)

    # Natural range of weighted composite
    min_possible = sum(LAYER_RANGES[k][0] * LAYER_WEIGHTS[k] for k in scores)
    max_possible = sum(LAYER_RANGES[k][1] * LAYER_WEIGHTS[k] for k in scores)

    normalized = normalize_to_10(raw_composite, min_possible, max_possible)

    # Build summary lines
    summary = []
    for layer_result, label in [
        (l1, "Trend (4H)"),
        (l2, "Momentum (1H)"),
        (l3, "Volume"),
        (l4, "Derivatives"),
        (l5, "Structure"),
    ]:
        if "summary" in layer_result:
            summary.extend(layer_result["summary"])

    return {
        "score": normalized,
        "raw_composite": round(raw_composite, 4),
        "layer_scores": scores,
        "layers": {
            "l1_trend":       l1,
            "l2_momentum":    l2,
            "l3_volume":      l3,
            "l4_derivatives": l4,
            "l5_structure":   l5,
        },
        "summary": summary,
        "is_bullish": normalized > 0,
        "pipeline": "TECHNICAL",
    }
