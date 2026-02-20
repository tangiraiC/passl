from dataclasses import dataclass
from routing.osrm_client import OSRMClient
from routing.geofence import geofence_candidates

@dataclass
class Rider:
    id: str
    lat: float
    lon: float

def main():
    osrm = OSRMClient(profile="driving", timeout=10)

    pickup = (52.517037, 13.388860)   # (lat, lon)
    dropoff = (52.529407, 13.397634)  # (lat, lon)

    riders = [
        Rider("r1", 52.518000, 13.389500),
        Rider("r2", 52.515800, 13.386000),
        Rider("r3", 52.525000, 13.410000),
    ]

    candidates = geofence_candidates(
        osrm=osrm,
        pickup=pickup,
        dropoff=dropoff,
        riders=riders,
        max_pickup_duration_s=900,
        max_pickup_distance_m=None,
        batch_size=100,
    )

    print(f"\nReturned {len(candidates)} candidates:\n")
    for c in candidates:
        print(
            f"{c.rider_id}: "
            f"pickup {c.pickup_duration_s:.1f}s, {c.pickup_distance_m:.1f}m | "
            f"dropoff {c.dropoff_duration_s:.1f}s, {c.dropoff_distance_m:.1f}m | "
            f"total {c.total_duration_s:.1f}s, {c.total_distance_m:.1f}m"
        )

if __name__ == "__main__":
    main()
