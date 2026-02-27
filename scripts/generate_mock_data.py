import pandas as pd
import numpy as np
import uuid
from datetime import datetime, timezone, timedelta

def generate_mock_orders(num_orders=1000, num_merchants=30, output_file="raw_orders_generated.csv"):
    """
    Generates a realistic dataset of delivery orders designed to test batching algorithms.
    It uses a fixed number of 'merchants' (pickups) to ensure multiple orders originate 
    from the same or nearby locations, which generates good realistic batching scenarios.
    """
    # Center around Harare, Zimbabwe (based on your previous test coordinates)
    CENTER_LAT = -17.824858
    CENTER_LON = 31.053028
    
    # 1. Generate fixed merchants (pickups) to force batching opportunities
    merchants = []
    for merchant_index in range(num_merchants):
        # Merchants placed within a ~5km radius (roughly 0.05 degrees)
        lat = CENTER_LAT + np.random.uniform(-0.05, 0.05)
        lon = CENTER_LON + np.random.uniform(-0.05, 0.05)
        merchants.append({
            "id": f"m_{str(uuid.uuid4())[:8]}",
            "name": f"Restaurant {merchant_index+1}",
            "lat": lat,
            "lon": lon
        })

    data = []
    now = datetime.now(timezone.utc)
    
    # 2. Generate Orders
    for order_index in range(num_orders):
        # Pick a random merchant for this order
        merchant = np.random.choice(merchants)
        
        # Dropoff placed within ~5-10km of the merchant (roughly 0.08 degrees)
        dropoff_lat = merchant["lat"] + np.random.uniform(-0.08, 0.08)
        dropoff_lon = merchant["lon"] + np.random.uniform(-0.08, 0.08)
        
        data.append({
            "order_id": f"o_{str(order_index+1).zfill(6)}",
            "created_at": (now - timedelta(minutes=np.random.randint(0, 60))).isoformat(),
            "customer_id": f"c_{np.random.randint(1000, 9999)}",
            "merchant_id": merchant["id"],
            "pickup_lat": np.round(merchant["lat"], 6),
            "pickup_lon": np.round(merchant["lon"], 6),
            "dropoff_lat": np.round(dropoff_lat, 6),
            "dropoff_lon": np.round(dropoff_lon, 6),
            "delivery_method": np.random.choice(["motorcycle", "car"], p=[0.8, 0.2]),
            "items_count": np.random.randint(1, 6),
            "weight_kg": np.round(np.random.uniform(0.5, 8.0), 1),
            "order_value_usd": np.round(np.random.uniform(5.0, 60.0), 2),
            "currency": "USD",
            "status": "RAW",
            "priority": np.random.choice([0, 1], p=[0.9, 0.1]),
            "pickup_address": merchant["name"]
        })

    # 3. Save to CSV
    df = pd.DataFrame(data)
    df.to_csv(output_file, index=False)
    print(f"✅ Generated {num_orders} orders and saved to '{output_file}'")
    
    # Print a quick preview of batching density
    print("\nTop 5 Merchants (Batching Potential):")
    counts = df['pickup_address'].value_counts().head(5)
    for name, count in counts.items():
        print(f"  {name}: {count} orders")

if __name__ == "__main__":
    generate_mock_orders(num_orders=1000, num_merchants=40)
