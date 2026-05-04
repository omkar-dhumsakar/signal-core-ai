import pandas as pd
import random

# Configuration for Goan context mock data
categories = ["FENI", "MANGO", "KOKUM", "CASHEW", "SPICE", "OIL", "GRAIN", "SNACK", "DAIRY", "BEV"]
regions = ["Mandovi", "Zuari", "Coastal", "Sahyadri", "North-Goa", "South-Goa"]
biz_types = ["Distributors", "Foods", "Agro Traders", "Logistics", "Industries"]
first_names = ["Rahul", "Sanjay", "Anjali", "Priya", "Amit", "Vikram", "Deepa", "Sunil", "Ricardo", "Maria"]
last_names = ["Naik", "Fernandes", "Prabhu", "Gomes", "D'Souza", "Pinto", "Kulkarni", "Sawant"]

data = []

for i in range(1, 5001):
    # Generate Unique SKU
    category = random.choice(categories)
    # Format: GOA-[CATEGORY]-[UNIQUE_ID]
    sku = f"GOA-{category}-{i:04d}"
    
    # Generate Supplier Info
    supplier = f"{random.choice(regions)} {random.choice(biz_types)}"
    
    # Lead Times (Normal vs. Monsoon)
    base_lead = random.randint(2, 4)
    monsoon_lead = base_lead + random.randint(2, 5) # Regional delay factor
    
    # Contact Details
    contact = f"{random.choice(first_names)} {random.choice(last_names)}"
    phone = f"+91 {random.randint(70000, 99999)} {random.randint(10000, 99999)}"
    
    data.append([sku, supplier, base_lead, monsoon_lead, contact, phone])

# Create DataFrame and Save to CSV
df = pd.DataFrame(data, columns=[
    "SKU", "Supplier_Name", "Lead_Time_Days", 
    "Monsoon_Lead_Time_Days", "Contact_Person", "Phone_Number"
])

df.to_csv("storeops_suppliers_5000.csv", index=False)
print(f"Successfully generated 5000 unique SKUs in 'storeops_suppliers_5000.csv'")
