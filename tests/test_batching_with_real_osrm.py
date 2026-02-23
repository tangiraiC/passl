import os
import pandas as pd
from pathlib import Path

from routing.osrm_client import OSRMClient
from routing.matrix_adapter import time_matrix_provider_from_osrm_client

from orders.models import Order
from orders.batching.engine import batch_orders
from orders.batching.policy import default_policy


class MockOSRM:
    def compute_table(self, sources, destinations):
        # Return a fake table based on rough manhattan distance
        # To make it simple, we just pretend 1 deg lat/lon = 100,000 meters = 10,000 seconds
        table = {}
        for i, s in enumerate(sources):
            for j, d in enumerate(destinations):
                dist = abs(s[0] - d[0]) + abs(s[1] - d[1])
                duration = dist * 10000 
                table[(i, j)] = {"duration": duration, "distance": dist * 100000}
        return table


def test_batching_real_osrm_dataset():

    # --- 1. OSRM Setup ---
    provider = time_matrix_provider_from_osrm_client(MockOSRM())

    # --- 2. Load your real dataset ---
    df = pd.read_csv("raw_orders_generated.csv")

    # Use small subset first 
    df = df.head(30)

    orders = []
    for _, row in df.iterrows():
        orders.append(
            Order(
                id=str(row["order_id"]),
                pickup=(row["pickup_lon"], row["pickup_lat"]),
                dropoff=(row["dropoff_lon"], row["dropoff_lat"]),
                pickup_id=str(row.get("pickup_address", row["pickup_lat"])),
            )
        )

    # --- 2.5 Mock Ages for Rolling Horizon ---
    # Give half the orders an age of 0 (Young) and half 300 (Old)
    # The default policy waits 180s before dispatching singles.
    ages = {}
    for i, o in enumerate(orders):
        ages[o.id] = 300.0 if i % 2 == 0 else 0.0

    # --- 3. Run batching ---
    result = batch_orders(
        orders,
        policy=default_policy(),
        stop_time_matrix_provider=provider,
        pickup_time_matrix_provider=provider,
        order_age_seconds=ages,
    )

    print(f"\\n--- Batching Results ---")
    print(f"Total Orders: {len(orders)}")
    print(f"Total Jobs created: {len(result.jobs)}")
    print(f"Total Unbatched left: {len(result.unbatched_orders)}\\n")

    for i, job in enumerate(result.jobs, 1):
        print(f"Job {i} ({job.job_type.value}):")
        print(f"  Orders: {', '.join(job.order_ids)}")
        print(f"  Detour ratio: {job.detour_factor or 1.0:.2f}")

    if result.unbatched_orders:
        print("\\nUnbatched Orders:")
        for o in result.unbatched_orders:
            print(f"  - {o.id}")

    assert len(result.jobs) > 0