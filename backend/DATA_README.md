# Data Directory

This directory contains the data files used by Signal Core AI.

## Included Files

- **`sample_data.csv`** — A small sample dataset with 20 SKUs × 3 stores (60 rows) for quick-start development and testing.
- **`test_suppliers.csv`** — Sample supplier data for testing the supplier upload API.

## Generating Larger Datasets

For testing at scale, you can generate synthetic datasets:

```bash
# Generate a Trimart-style dataset (500 SKUs × 20 stores)
python generate_trimart.py

# Generate a supplier database (5,000 suppliers)
python generate_suppliers.py
```

## Using Your Own Data

Signal Core AI expects a CSV with the following columns:

| Column | Type | Description |
|--------|------|-------------|
| `sku_id` | string | Unique SKU identifier |
| `sku_name` | string | Product display name |
| `category` | string | Product category |
| `daily_sales` | float | Average daily sales volume |
| `supplier_lead_time_days` | int | Supplier lead time in days |
| `store_id` | string | Store identifier |

Place your CSV in this directory and update the `rl_bridge.py` data loader path to point to it.

## Dataset Scale Guidelines

| Scale | SKUs | Recommended Engine |
|-------|------|--------------------|
| Development | 20–100 | Tabular Q-Learning |
| Medium | 100–1,000 | Tabular Q-Learning |
| Enterprise | 1,000–40,000+ | DQN (Deep Q-Network) |
