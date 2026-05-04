import pandas as pd
import numpy as np


def generate_demand_signals(days=365, base_demand=5000, lead_time=3):
    """
    Generates synthetic demand with periodic promotion spikes.
    Fixed: Explicit casting to int to prevent UFuncOutputCastingError.
    """
    dates = pd.date_range(start="2024-01-01", periods=days)
    demand = np.random.normal(base_demand, base_demand * 0.15, days).astype(int)

    # Introduce promotion spikes every 14 days
    promo_signals = np.zeros(days)
    for i in range(0, days, 14):
        # FIX: Explicitly cast the float result to int before in-place addition
        spike_value = int(base_demand * 1.5)
        demand[i:i + 3] += spike_value
        promo_signals[i:i + 3] = 1

    # The 'Lookahead' signal: AI sees the promo 'lead_time' days early
    lookahead_signal = np.roll(promo_signals, -lead_time)
    lookahead_signal[-lead_time:] = 0

    df = pd.DataFrame({
        'Date': dates,
        'Demand': np.maximum(0, demand),
        'Promo_Signal': lookahead_signal,
        'Actual_Promo': promo_signals
    })
    return df


def load_sku_demand_profiles(csv_path: str) -> dict:
    """Load real per-SKU demand profiles from a retail CSV.

    Aggregates daily_sales across all stores for each SKU, producing a
    demand time-series and auto-detected promo signals.

    Returns
    -------
    dict[str, dict]
        {sku_id: {
            "demand": np.ndarray,          # daily demand (aggregated across stores)
            "promo_signal": np.ndarray,     # 1 where demand spikes > 2σ
            "avg_daily_sales": float,
            "avg_lead_time": float,
            "category": str,
            "sku_name": str,
        }}
    """
    import os

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)

    # Aggregate daily sales across all stores per SKU per day
    agg = df.groupby(["sku_id", "date"]).agg(
        total_sales=("daily_sales", "sum"),
    ).reset_index()

    # Per-SKU metadata (category, name, lead time)
    meta = df.groupby("sku_id").agg(
        sku_name=("sku_name", "first"),
        category=("category", "first"),
        avg_daily_sales=("daily_sales", "mean"),
        avg_lead_time=("supplier_lead_time_days", "mean"),
    ).reset_index()

    profiles = {}
    for _, row in meta.iterrows():
        sku = row["sku_id"]
        sku_demand = agg[agg["sku_id"] == sku].sort_values("date")
        demand = sku_demand["total_sales"].values.astype(float)

        # Auto-detect promo spikes: days where demand > mean + 2*std
        mean_d = demand.mean()
        std_d = demand.std()
        threshold = mean_d + 2 * std_d if std_d > 0 else mean_d * 1.5
        promo_signal = (demand > threshold).astype(float)

        # Add lookahead: shift promo signal back by avg lead time
        lead = max(1, int(round(row["avg_lead_time"])))
        lookahead = np.roll(promo_signal, -lead)
        lookahead[-lead:] = 0

        profiles[sku] = {
            "demand": demand,
            "promo_signal": lookahead,
            "avg_daily_sales": float(row["avg_daily_sales"]),
            "avg_lead_time": float(row["avg_lead_time"]),
            "category": row["category"],
            "sku_name": row["sku_name"],
        }

    return profiles