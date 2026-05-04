"""Generate a synthetic BigBasket-scale dataset with 40,000 SKUs.

Produces a CSV matching the rl_bridge.py expected schema:
  sku_id, sku_name, category, daily_sales, supplier_lead_time_days, store_id

Categories and product names mirror BigBasket's real catalog structure.
Each SKU is replicated across 6 BB Bengaluru stores with slight sales variance.
"""

import csv
import random
import os

random.seed(42)

# BigBasket's real category taxonomy with representative products
BB_CATEGORIES = {
    "Fruits & Vegetables": {
        "count": 6000,
        "products": [
            "Banana Robusta", "Tomato Local", "Onion", "Potato", "Green Chilli",
            "Cucumber", "Carrot", "Capsicum Green", "Beetroot", "Brinjal",
            "Ladies Finger", "Cauliflower", "Cabbage", "Spinach", "Coriander Leaves",
            "Curry Leaves", "Mint Leaves", "Lemon", "Ginger", "Garlic",
            "Sweet Corn", "Mushroom Button", "Baby Corn", "Avocado", "Pomegranate",
            "Apple Shimla", "Orange Nagpur", "Grapes Green", "Watermelon", "Papaya",
            "Mango Alphonso", "Mango Kesar", "Sapota Chikoo", "Guava", "Pineapple",
            "Strawberry", "Blueberry", "Jackfruit", "Coconut", "Dragon Fruit",
            "Kiwi", "Pear", "Plum", "Peach", "Fig Fresh",
            "Sweet Potato", "Drumstick", "Radish", "Cluster Beans", "Ridge Gourd",
            "Bottle Gourd", "Bitter Gourd", "Snake Gourd", "Ash Gourd", "Raw Banana",
            "Yam", "Colocasia", "Broadbeans", "French Beans", "Peas Green",
        ],
        "lead_time": (1, 3),
        "daily_sales": (5, 200),
    },
    "Dairy & Eggs": {
        "count": 4500,
        "products": [
            "Nandini Toned Milk 500ml", "Amul Gold Milk 1L", "Heritage Full Cream 500ml",
            "Nandini Curd 400g", "Amul Masti Dahi 400g", "Mother Dairy Curd 500g",
            "Amul Butter 500g", "Nandini Butter 100g", "Britannia Cheese Slices",
            "Amul Paneer 200g", "Milky Mist Paneer 500g", "Fresh Tofu 200g",
            "Amul Fresh Cream 200ml", "Nestle Cream 200g", "Whipping Cream 200ml",
            "Farm Fresh Eggs 6pc", "Country Eggs 6pc", "Kadaknath Eggs 6pc",
            "Greek Yogurt Plain", "Greek Yogurt Strawberry", "Lassi Mango 200ml",
            "Chaas Masala 200ml", "Milkshake Chocolate 200ml", "Shrikhand 100g",
            "Condensed Milk 200g", "Ghee Nandini 1L", "Ghee Amul 500ml",
            "Flavoured Milk Badam", "Flavoured Milk Elaichi", "Khoa Fresh 250g",
        ],
        "lead_time": (1, 2),
        "daily_sales": (10, 300),
    },
    "Staples & Grains": {
        "count": 5000,
        "products": [
            "Toor Dal 1kg", "Moong Dal 1kg", "Chana Dal 500g", "Urad Dal 1kg",
            "Masoor Dal 500g", "Basmati Rice 5kg", "Sona Masoori Rice 5kg",
            "Ponni Rice 5kg", "Brown Rice 1kg", "Wheat Flour Aashirvaad 5kg",
            "Wheat Flour Pillsbury 1kg", "Maida 1kg", "Besan 500g", "Rava Sooji 500g",
            "Poha 500g", "Ragi Flour 500g", "Jowar Flour 500g", "Multigrain Atta 5kg",
            "Vermicelli 500g", "Sago Sabudana 500g", "Corn Flour 200g",
            "Sugar 1kg", "Jaggery 500g", "Rock Salt 1kg", "Iodised Salt 1kg",
            "Sunflower Oil 1L", "Groundnut Oil 1L", "Mustard Oil 1L",
            "Olive Oil Extra Virgin 500ml", "Coconut Oil 1L", "Rice Bran Oil 1L",
            "Sesame Oil 500ml", "Soyabean Oil 1L", "Palm Oil 1L",
        ],
        "lead_time": (3, 7),
        "daily_sales": (8, 150),
    },
    "Beverages": {
        "count": 3500,
        "products": [
            "Bisleri Water 1L", "Kinley Water 1L", "Himalayan Water 1L",
            "Coca Cola 750ml", "Pepsi 750ml", "Sprite 750ml", "Fanta 750ml",
            "Thumbs Up 750ml", "Limca 750ml", "Maaza 600ml",
            "Real Juice Mixed Fruit 1L", "Tropicana Orange 1L", "Paper Boat Aamras",
            "Red Bull 250ml", "Monster Energy 350ml", "Sting 250ml",
            "Nescafe Classic 50g", "Bru Instant Coffee 50g", "Filter Coffee 200g",
            "Tata Tea Premium 250g", "Taj Mahal Tea 250g", "Green Tea Organic",
            "Chamomile Tea 25bags", "Masala Chai Mix 200g", "Horlicks 500g",
            "Bournvita 500g", "Complan 500g", "Boost 500g",
            "Coconut Water 200ml", "Buttermilk 200ml", "Soda Water 750ml",
        ],
        "lead_time": (3, 7),
        "daily_sales": (5, 120),
    },
    "Bakery & Snacks": {
        "count": 4000,
        "products": [
            "Britannia Bread White", "Harvest Gold Brown Bread", "Multigrain Bread",
            "Britannia Good Day 200g", "Parle-G 200g", "Sunfeast Dark Fantasy",
            "Oreo Original 120g", "Hide & Seek 200g", "McVities Digestive",
            "Lays Classic Salted 52g", "Kurkure Masala Munch", "Bingo Mad Angles",
            "Haldirams Aloo Bhujia 200g", "Haldirams Namkeen Mix", "Bikano Rasgulla",
            "Cadbury Dairy Milk 50g", "KitKat 37.3g", "5 Star 40g",
            "Muffin Chocolate", "Croissant Butter", "Puff Veg",
            "Samosa Frozen 4pc", "Spring Roll Frozen", "Garlic Bread Frozen",
            "Popcorn Butter 80g", "Nachos Cheese", "Trail Mix 200g",
            "Protein Bar 60g", "Granola Bar 30g", "Energy Bar Dates",
        ],
        "lead_time": (2, 5),
        "daily_sales": (5, 100),
    },
    "Meat & Seafood": {
        "count": 2500,
        "products": [
            "Chicken Breast Boneless 500g", "Chicken Thigh 500g", "Chicken Drumstick 500g",
            "Chicken Wings 500g", "Whole Chicken 1kg", "Chicken Keema 500g",
            "Mutton Curry Cut 500g", "Mutton Keema 500g", "Mutton Chops 500g",
            "Fish Rohu 500g", "Fish Surmai 500g", "Fish Pomfret 500g",
            "Prawns Medium 500g", "Prawns Large 250g", "Crab Whole 500g",
            "Squid Rings 250g", "Fish Fillet Basa 500g", "Salmon Fillet 200g",
            "Chicken Sausage 250g", "Pork Sausage 250g", "Salami Chicken 200g",
            "Bacon Chicken 200g", "Ham Smoked 200g", "Turkey Breast 250g",
            "Egg Boiled 6pc", "Chicken Seekh Kebab", "Fish Finger Frozen",
        ],
        "lead_time": (1, 2),
        "daily_sales": (3, 80),
    },
    "Spices & Masala": {
        "count": 3000,
        "products": [
            "Turmeric Powder 200g", "Red Chilli Powder 200g", "Coriander Powder 200g",
            "Cumin Powder 100g", "Garam Masala 100g", "Sambar Powder 200g",
            "Rasam Powder 100g", "Biryani Masala 100g", "Chicken Masala 100g",
            "Pav Bhaji Masala 100g", "Chaat Masala 100g", "Kitchen King Masala",
            "Black Pepper Whole 50g", "Cumin Seeds 100g", "Mustard Seeds 100g",
            "Fenugreek Seeds 100g", "Fennel Seeds 100g", "Cardamom Green 50g",
            "Cloves Whole 50g", "Cinnamon Stick 50g", "Bay Leaves 50g",
            "Star Anise 50g", "Nutmeg Whole 50g", "Saffron 1g",
            "Tamarind Paste 200g", "Tomato Paste 200g", "Ginger Garlic Paste 200g",
        ],
        "lead_time": (5, 10),
        "daily_sales": (3, 60),
    },
    "Personal Care": {
        "count": 4000,
        "products": [
            "Dove Soap 100g", "Lux Soap 100g", "Dettol Soap 125g",
            "Dove Shampoo 340ml", "Head & Shoulders 340ml", "Pantene 340ml",
            "Colgate MaxFresh 150g", "Pepsodent 150g", "Sensodyne 70g",
            "Nivea Body Lotion 200ml", "Vaseline Lotion 200ml", "Pond's Cream 100g",
            "Gillette Razor", "Venus Razor", "Veet Hair Removal 60g",
            "Sunscreen SPF50 50ml", "Face Wash Himalaya 150ml", "Face Wash Garnier",
            "Deodorant Axe 150ml", "Deodorant Dove 150ml", "Perfume Fogg 120ml",
            "Hand Sanitizer 200ml", "Hand Wash Lifebuoy 200ml", "Baby Lotion 200ml",
            "Baby Shampoo 200ml", "Diaper Pampers M 10pc", "Cotton Pads 80pc",
        ],
        "lead_time": (5, 14),
        "daily_sales": (2, 50),
    },
    "Household Items": {
        "count": 3500,
        "products": [
            "Surf Excel 1kg", "Ariel 1kg", "Tide 1kg", "Rin Bar 250g",
            "Vim Bar 200g", "Vim Liquid 500ml", "Harpic 500ml",
            "Lizol Floor Cleaner 500ml", "Colin Glass Cleaner 500ml",
            "Odonil Air Freshener", "Good Knight Liquid Refill", "All Out Refill",
            "Garbage Bags Large 30pc", "Aluminium Foil 9m", "Cling Wrap 30m",
            "Kitchen Tissue Roll", "Toilet Paper Roll 4pc", "Wet Wipes 80pc",
            "Broom Soft", "Mop Floor", "Scrub Pad 3pc",
            "Detergent Liquid 1L", "Fabric Softener 500ml", "Bleach 500ml",
            "Steel Wool 6pc", "Sponge 3pc", "Dustpan Set",
        ],
        "lead_time": (5, 14),
        "daily_sales": (2, 40),
    },
    "Dry Fruits & Nuts": {
        "count": 2000,
        "products": [
            "Cashew Whole 250g", "Cashew Broken 500g", "Almond California 250g",
            "Walnut Kernel 250g", "Pistachio Roasted 200g", "Peanut Raw 500g",
            "Raisin Green 250g", "Raisin Black 250g", "Dried Apricot 200g",
            "Dried Fig 200g", "Dates Medjool 250g", "Dates Seedless 500g",
            "Prune 200g", "Cranberry Dried 200g", "Mixed Dry Fruits 250g",
            "Flax Seeds 200g", "Chia Seeds 200g", "Pumpkin Seeds 200g",
            "Sunflower Seeds 200g", "Watermelon Seeds 200g", "Trail Mix 200g",
        ],
        "lead_time": (7, 14),
        "daily_sales": (1, 30),
    },
    "Baby & Kids": {
        "count": 1500,
        "products": [
            "Cerelac Wheat 300g", "Cerelac Rice 300g", "Lactogen 1 400g",
            "Similac 1 400g", "Enfamil 400g", "Nan Pro 1 400g",
            "Pampers Pants M 38pc", "Huggies Pants M 34pc", "MamyPoko L 30pc",
            "Baby Wipes 72pc", "Baby Oil 200ml", "Baby Powder 400g",
            "Gripe Water 130ml", "Baby Soap 75g", "Baby Shampoo 200ml",
            "Sippy Cup", "Baby Bowl Set", "Teether",
        ],
        "lead_time": (5, 10),
        "daily_sales": (1, 25),
    },
    "Cleaning & Laundry": {
        "count": 500,
        "products": [
            "Phenyl 1L", "Bathroom Cleaner 500ml", "Kitchen Cleaner 500ml",
            "Drain Cleaner 500ml", "Carpet Cleaner 500ml", "Shoe Polish",
            "Starch Spray", "Fabric Stain Remover", "Toilet Bowl Cleaner",
            "Glass Cleaner Refill", "Mop Refill Head", "Broom Grass",
        ],
        "lead_time": (7, 14),
        "daily_sales": (1, 20),
    },
}

BB_STORES = [
    "CDC-BLR-CENTRAL",
    "DS-BLR-KORAMANGALA",
    "DS-BLR-HSR",
    "DS-BLR-INDIRANAGAR",
    "DS-BLR-WHITEFIELD",
    "HUB-BLR-JAYANAGAR",
]

OUTPUT_PATH = os.path.join(
    os.path.dirname(__file__),
    "bigbasket_40k_skus_bengaluru.csv",
)


def generate():
    rows = []
    sku_counter = 0

    for category, config in BB_CATEGORIES.items():
        target = config["count"]
        products = config["products"]
        lt_lo, lt_hi = config["lead_time"]
        ds_lo, ds_hi = config["daily_sales"]

        for i in range(target):
            sku_counter += 1
            base_product = products[i % len(products)]

            # Create variants (sizes, brands, organic versions)
            variant_idx = i // len(products)
            suffixes = ["", " - Large", " - Small", " - Premium", " - Organic",
                        " - Value Pack", " - Family Pack", " - Economy",
                        " - XL", " - Mini", " - Bulk", " - Fresh",
                        " - Natural", " - Double", " - Lite"]
            suffix = suffixes[variant_idx % len(suffixes)]
            product_name = f"{base_product}{suffix}"

            sku_id = f"BB-{sku_counter:06d}"
            lead_time = random.randint(lt_lo, lt_hi)

            # Each SKU appears in all 6 stores with varying sales
            for store in BB_STORES:
                # CDC has higher volume, dark stores have location variance
                multiplier = 2.0 if store.startswith("CDC") else random.uniform(0.5, 1.5)
                daily_sales = round(random.uniform(ds_lo, ds_hi) * multiplier, 1)

                rows.append({
                    "sku_id": sku_id,
                    "sku_name": product_name,
                    "category": category,
                    "daily_sales": daily_sales,
                    "supplier_lead_time_days": lead_time,
                    "store_id": store,
                })

    # Shuffle for realism
    random.shuffle(rows)

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "sku_id", "sku_name", "category", "daily_sales",
            "supplier_lead_time_days", "store_id",
        ])
        writer.writeheader()
        writer.writerows(rows)

    unique_skus = len(set(r["sku_id"] for r in rows))
    total_rows = len(rows)
    print(f"[OK] Generated {OUTPUT_PATH}")
    print(f"   {unique_skus:,} unique SKUs × {len(BB_STORES)} stores = {total_rows:,} rows")
    print(f"   Categories: {len(BB_CATEGORIES)}")
    return unique_skus, total_rows


if __name__ == "__main__":
    generate()
