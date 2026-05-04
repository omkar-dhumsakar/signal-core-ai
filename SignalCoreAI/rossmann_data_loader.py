import pandas as pd
import numpy as np


def load_rossmann_data(csv_path="train.csv", store_path="store.csv", store_id=1):
    train = pd.read_csv(csv_path, low_memory=False)
    store = pd.read_csv(store_path)
    train.columns = train.columns.str.replace('"', '').str.strip()
    train['Date'] = pd.to_datetime(train['Date'])

    # Context-Aware Merge
    df = train[train['Store'] == store_id].merge(store[store['Store'] == store_id], on='Store')
    df = df.sort_values('Date')
    df = df[df['Open'] != 0]
    return df


def prepare_rossmann_arrays(df, lead_time=3, noise_level=0.15):
    demand = df['Sales'].values
    noise = np.random.normal(1.0, noise_level, size=len(demand))
    stress_demand = np.maximum(0, demand * noise).astype(int)

    # Signals
    p1 = np.roll(df['Promo'].astype(int).values, -lead_time)
    p1[-lead_time:] = 0

    comp_dist = df['CompetitionDistance'].fillna(10000).values[0]
    assortment = {'a': 1, 'b': 2, 'c': 3}.get(df['Assortment'].values[0], 1)

    promo2_active = np.zeros(len(df))
    if df['Promo2'].values[0] == 1:
        intervals = str(df['PromoInterval'].values[0]).split(',')
        month_map = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6, 'Jul': 7, 'Aug': 8, 'Sept': 9,
                     'Oct': 10, 'Nov': 11, 'Dec': 12}
        active_months = [month_map.get(m.strip()) for m in intervals if m.strip() in month_map]
        promo2_active = df['Date'].dt.month.isin(active_months).astype(int).values

    return stress_demand, p1, promo2_active, {'comp_dist': comp_dist, 'assortment': assortment}