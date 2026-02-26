"""
Purpose: Business rules and distance math for choosing the absolute best driver.
What it does:
Accepts a Job and a pool of drivers, filters out ineligible drivers,
and ranks the remaining ones (e.g., closest ETA to pickup).
"""

from typing import List, Optional, Tuple, Any
from .models import Driver, DriverStatus
from .policy import DriverPolicy, default_driver_policy

def filter_eligible_drivers(drivers: List[Driver], required_capacity: int = 1) -> List[Driver]:
    """
    Returns only drivers who are online, available, and have 
    enough capacity to handle the job's order count.
    """
    eligible = []
    
    for driver in drivers:
        if driver.status != DriverStatus.AVAILABLE:
            continue
            
        if driver.max_capacity < required_capacity:
            continue
            
        eligible.append(driver)
        
    return eligible

def build_driver_waves(
    pickup_location: Tuple[float, float], 
    drivers: List[Driver], 
    required_capacity: int = 1,
    policy: Optional[DriverPolicy] = None,
    time_matrix_provider: Optional[Any] = None
) -> List[List[Driver]]:
    """
    Given a pickup location, filter out ineligible drivers and group the rest
    into 5 concentric distance waves.
    
    If highly accurate OSRM ETA is needed in production instead of Cartesian math,
    pass the `time_matrix_provider` (e.g. PreloadingTimeMatrixProvider) into this function.
    """
    policy = policy or default_driver_policy()
    
    eligible = filter_eligible_drivers(drivers, required_capacity)
    
    # Initialize 5 empty waves
    waves: List[List[Driver]] = [[], [], [], [], []]
    
    if not eligible:
        return waves
        
    pickup_latitude, pickup_longitude = pickup_location
    
    # --- OSRM EXACT ROUTING APPROACH ---
    if time_matrix_provider:
        # Pre-fetch all locations in one giant bulk request to prevent NHTTP calls
        all_coords = [pickup_location] + [d.location for d in eligible]
        if hasattr(time_matrix_provider, "prefetch"):
            time_matrix_provider.prefetch(all_coords)
            
        times_matrix = time_matrix_provider(all_coords) # Returns N x N array
        
        # OSRM Matrix indexing: 0 is the pickup location. 1 through N are the eligible drivers.
        # We only care about time from Driver -> Pickup.
        
        for idx, driver in enumerate(eligible):
            driver_idx = idx + 1 
            # Duration in exact seconds for the driver to reach the pickup location
            duration_sec = times_matrix[driver_idx][0]
            
            etas = policy.wave_eta_seconds
            if duration_sec <= etas[0]:
                waves[0].append(driver)
            elif duration_sec <= etas[1]:
                waves[1].append(driver)
            elif duration_sec <= etas[2]:
                waves[2].append(driver)
            elif duration_sec <= etas[3]:
                waves[3].append(driver)
            elif duration_sec <= etas[4]:
                waves[4].append(driver)

        # Sort each wave internally by literal route ETA (closest to furthest)
        for wave in waves:
            wave.sort(key=lambda d: time_matrix_provider([d.location, pickup_location])[0][1])
            
        return waves
        
    # --- CARTESIAN FALLBACK APPROACH ---
    for driver in eligible:
        driver_latitude, driver_longitude = driver.location
        
        # Fast pythagorean approximation for initial radius buckets
        distance_degrees = ((pickup_latitude - driver_latitude) ** 2 + (pickup_longitude - driver_longitude) ** 2) ** 0.5
        
        # Sort into 5 cascading waves based on approx radius defined in Policy
        radii = policy.wave_radii_degrees
        if distance_degrees <= radii[0]:      
            waves[0].append(driver)
        elif distance_degrees <= radii[1]:    
            waves[1].append(driver)
        elif distance_degrees <= radii[2]:    
            waves[2].append(driver)
        elif distance_degrees <= radii[3]:    
            waves[3].append(driver)
        elif distance_degrees <= radii[4]:    
            waves[4].append(driver)
            
    # Sort each wave natively by distance to ensure best in sub-group is first
    for wave in waves:
        wave.sort(
            key=lambda current_driver: (
                (pickup_latitude - current_driver.location[0]) ** 2 + 
                (pickup_longitude - current_driver.location[1]) ** 2
            ) ** 0.5
        )
            
    # Cap each wave to a maximum of 5 drivers to prevent over-broadcasting
    for i in range(len(waves)):
        waves[i] = waves[i][:5]
            
    return waves
