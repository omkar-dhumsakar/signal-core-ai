import pandas as pd
import random

# Categories and their sub-attributes
categories = {
    'Staples': {'sub': ['Rice', 'Dal', 'Oil', 'Flour'], 'mrp': (50, 1000), 'margin': 0.15, 'lt': (1, 3)},
    'FMCG': {'sub': ['Soap', 'Shampoo', 'Snacks', 'Biscuits'], 'mrp': (10, 500), 'margin': 0.08, 'lt': (3, 5)},
    'General': {'sub': ['Kitchen', 'Toys', 'Bedding'], 'mrp': (100, 2000), 'margin': 0.25, 'lt': (7, 12)},
    'Apparel': {'sub': ['Mens', 'Womens', 'Kids'], 'mrp': (199, 1200), 'margin': 0.40, 'lt': (10, 15)}
}

data = []
for i in range(1, 5001):
    cat = random.choice(list(categories.keys()))
    mrp = random.randint(*categories[cat]['mrp'])
    price = int(mrp * (1 - categories[cat]['margin']))
    lt = random.randint(*categories[cat]['lt'])
    
    data.append({
        'SKU_ID': f"DM-{cat[0]}{i:04d}",
        'Product_Name': f"{cat} Item {i}",
        'Category': cat,
        'Sub_Category': random.choice(categories[cat]['sub']),
        'MRP': mrp,
        'Store_Price': price,
        'Lead_Time_Days': lt,
        'Inventory_Turn': random.randint(15, 45) # D-Mart average is ~31
    })

df = pd.DataFrame(data)
df.to_csv('Trimart_StoreOps_Master.csv', index=False)
print(f"Successfully generated {len(df)} rows in 'Trimart_StoreOps_Master.csv'")
print(f"\nColumns: {list(df.columns)}")
print(f"\nCategory distribution:\n{df['Category'].value_counts()}")
print(f"\nSample rows:\n{df.head()}")
