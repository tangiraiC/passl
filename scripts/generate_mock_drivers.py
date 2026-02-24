import csv
import random

def generate_mock_drivers(filename="mock_drivers_100.csv", count=100):
    # Base coordinate roughly mapping to the center of Harare from the orders CSV.
    # Orders are typically clustered around -17.82, 31.05
    base_lat = -17.824858
    base_lon = 31.053028
    
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["driver_id", "lat", "lon", "status", "max_capacity"])
        
        for i in range(count):
            driver_id = f"DRV-{str(i+1).zfill(3)}"
            
            # Scatter drivers randomly around the city center (roughly +/- 10km)
            lat = base_lat + (random.random() - 0.5) * 0.15
            lon = base_lon + (random.random() - 0.5) * 0.15
            
            # 80% chance of being available, 20% offline
            status = "available" if random.random() < 0.8 else "offline"
            
            # Random max capacity between 2 and 5 orders
            capacity = random.randint(2, 5)
            
            writer.writerow([driver_id, round(lat, 6), round(lon, 6), status, capacity])
            
    print(f"Successfully generated {count} mock drivers into '{filename}'.")

if __name__ == "__main__":
    generate_mock_drivers()
