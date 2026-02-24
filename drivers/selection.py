"""
Purpose: Business rules and distance math for choosing the absolute best driver.
What it does:
Accepts a Job and a pool of drivers, filters out ineligible drivers,
and ranks the remaining ones (e.g., closest ETA to pickup).
"""

from typing import List, Optional, Tuple
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
    policy: Optional[DriverPolicy] = None
) -> List[List[Driver]]:
    """
    Given a pickup location, filter out ineligible drivers and group the rest
    into 5 concentric distance waves.
    
    Wave 1: Extemely close (e.g. radii threshold 0)
    Wave 2: Very close (e.g. radii threshold 1)
    Wave 3: Close (e.g. radii threshold 2)
    Wave 4: Medium (e.g. radii threshold 3)
    Wave 5: Far / Hail Mary (e.g. radii threshold 4)
    
    If highly accurate OSRM ETA is needed in production instead of Cartesian math,
    pass the `PreloadingTimeMatrixProvider` into this function.
    """
    policy = policy or default_driver_policy()
    
    eligible = filter_eligible_drivers(drivers, required_capacity)
    
    # Initialize 5 empty waves
    waves: List[List[Driver]] = [[], [], [], [], []]
    
    if not eligible:
        return waves
        
    pickup_latitude, pickup_longitude = pickup_location
    
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
            
    return waves
