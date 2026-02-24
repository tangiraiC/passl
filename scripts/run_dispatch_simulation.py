import csv
import os
import random
import time
from typing import List

from orders.batching.engine import batch_orders
from orders.batching.policy import BatchingPolicy
from orders.models import Order
from routing.osrm_client import OSRMClient
from routing.matrix_adapter import PreloadingTimeMatrixProvider
from drivers.models import Driver
from dispatch.dispatcher import Dispatcher

class MockPushService:
    def __init__(self, output_writer):
        self.output_writer = output_writer
        
    def broadcast_offer(self, driver_ids, job):
        pass # Silently model notifications for the test output later.
        
    def revoke_offer(self, driver_ids, job_id):
        pass

def load_orders(filepath="raw_orders_generated.csv", limit=50) -> List[Order]:
    orders = []
    
    # Resolve the correct path depending on where the user runs the script from.
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    absolute_path = os.path.join(base_dir, filepath)
    
    with open(absolute_path, 'r') as file:
        reader = csv.DictReader(file)
        count = 0
        for row in reader:
            if count >= limit: break
            orders.append(
                Order(
                    id=row['order_id'],
                    pickup=(float(row['pickup_lat']), float(row['pickup_lon'])),
                    dropoff=(float(row['dropoff_lat']), float(row['dropoff_lon'])),
                    pickup_id=row['merchant_id']
                )
            )
            count += 1
    return orders

def load_drivers(filepath="scripts/mock_drivers_100.csv") -> List[Driver]:
    drivers = []
    
    # Resolve the correct path depending on where the user runs the script from.
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    absolute_path = os.path.join(base_dir, filepath)
    
    with open(absolute_path, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            drivers.append(
                Driver.new(
                    row['driver_id'],
                    float(row['lat']),
                    float(row['lon']),
                    row['status'],
                    int(row['max_capacity'])
                )
            )
    return drivers

def run_simulation():
    print("=== STARTING END-TO-END DISPATCH SIMULATION ===")
    
    # 1. Load Data
    orders = load_orders("raw_orders_generated.csv", limit=30) 
    drivers = load_drivers("mock_drivers_100.csv")
    print(f"Loaded {len(orders)} Orders and {len(drivers)} Drivers.\n")
    
    # 2. Configure System
    policy = BatchingPolicy(
        max_batch_size=5, # Allow up to 5 orders per driver
        enable_continuous_chaining=True
    )
    osrm_client = OSRMClient()
    matrix_provider = PreloadingTimeMatrixProvider(osrm_client)
    
    # 3. Step 1: Execute The Orders Batching Engine
    print("Running OSRM Combinatorics Batching Engine...")
    start_time = time.time()
    batch_result = batch_orders(
        orders, 
        policy=policy,
        stop_time_matrix_provider=matrix_provider
    )
    print(f"Engine built {len(batch_result.jobs)} Optimized Jobs in {time.time() - start_time:.2f}s.\n")
    # For reporting metrics
    total_unbatched = len(batch_result.unbatched_orders)
    batched_orders = 30 - total_unbatched
    
    # 4. Step 2: Dispatch the Jobs through the 5-Wave Pipeline
    print("Executing 5-Wave Dispatch Broadcasts...")
    
    # Save next to the script
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_path = os.path.join(base_dir, "dispatch_results.csv")
    
    with open(output_path, "w", newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["job_id", "orders_in_job", "accepted_by_driver", "wave_number", "detour_metric"])
        
        dispatcher = Dispatcher(push_service=MockPushService(writer))
        
        successful_dispatches = 0
        
        from drivers.selection import build_driver_waves
        
        for job in batch_result.jobs:
            waves = build_driver_waves(
                pickup_location=job.stops[0].coord, 
                drivers=drivers, 
                required_capacity=len(job.order_ids)
            )
            
            job_accepted = False
            for wave_index, wave in enumerate(waves):
                if not wave: continue
                
                # Simulate a driver deciding to accept.
                # In Wave 1, there's a 30% chance someone hits accept before the 30s timeout.
                # In Wave 2, 50% chance, etc. (Model simulating race conditions).
                acceptance_probability = 0.3 + (wave_index * 0.15)
                
                if random.random() < acceptance_probability:
                    # Simulation: Someone clicked accept!
                    winner = random.choice(wave)
                    job_accepted = True
                    successful_dispatches += 1
                    
                    # Log the resolution
                    writer.writerow([
                        job.job_id, 
                        len(job.order_ids), 
                        winner.id, 
                        wave_index + 1, 
                        round(job.metrics.detour_ratio, 2) if hasattr(job, 'metrics') and hasattr(job.metrics, 'detour_ratio') else "N/A"
                    ])
                    print(f"[SUCCESS] Job {job.job_id.split('-')[1]} (Size: {len(job.order_ids)}) -> Assigned to {winner.id} (Wave {wave_index + 1})")
                    break
            
            if not job_accepted:
                writer.writerow([job.job_id, len(job.order_ids), "FAILED", "ALL_WAVES_EXHAUSTED", "N/A"])
                print(f"[FAILED] Job {job.job_id.split('-')[1]} -> No drivers accepted across 5 waves.")

    print("\n=== SIMULATION COMPLETE ===")
    print(f"Orders Grouped: {batched_orders} / {batched_orders + total_unbatched}")
    print(f"Jobs Dispatched: {successful_dispatches} / {len(batch_result.jobs)}")
    print("Results written to 'dispatch_results.csv'.")

if __name__ == "__main__":
    run_simulation()
