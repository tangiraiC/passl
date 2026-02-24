"""
Purpose: Business rules and distance math for choosing the absolute best driver.
What it does:
Accepts a Job and a pool of drivers, filters out ineligible drivers,
and ranks the remaining ones (e.g., closest ETA to pickup).
"""

from typing import List, Optional, Tuple
from .models import Driver, DriverStatus

def filter_eligible_drivers(drivers: List[Driver], required_capacity: int = 1) -> List[Driver]:
    """
    Returns only drivers who are online, available, and have 
    enough capacity to handle the job's order count.
    """
    eligible = []
    
    for d in drivers:
        if d.status != DriverStatus.AVAILABLE:
            continue
            
        if d.max_capacity < required_capacity:
            continue
            
        eligible.append(d)
        
    return eligible

def build_driver_waves(
    pickup_location: Tuple[float, float], 
    drivers: List[Driver], 
    required_capacity: int = 1,
) -> List[List[Driver]]:
    """
    Given a pickup location, filter out ineligible drivers and group the rest
    into 5 concentric distance waves.
    
    Wave 1: Extemely close (e.g. 0-2 km approx)
    Wave 2: Very close (e.g. 2-4 km)
    Wave 3: Close (e.g. 4-6 km)
    Wave 4: Medium (e.g. 6-8 km)
    Wave 5: Far / Hail Mary (e.g. 8-10 km)
    
    If highly accurate OSRM ETA is needed in production instead of Cartesian math,
    pass the `PreloadingTimeMatrixProvider` into this function.
    """
    
    eligible = filter_eligible_drivers(drivers, required_capacity)
    
    # Initialize 5 empty waves
    waves: List[List[Driver]] = [[], [], [], [], []]
    
    if not eligible:
        return waves
        
    plat, plon = pickup_location
    
    for d in eligible:
        dlat, dlon = d.location
        
        # Fast pythagorean approximation for initial radius buckets
        dist = ((plat - dlat) ** 2 + (plon - dlon) ** 2) ** 0.5
        
        # Sort into 5 cascading waves based on approx radius
        if dist <= 0.02:      # Wave 1 (~2km)
            waves[0].append(d)
        elif dist <= 0.04:    # Wave 2 (~4km)
            waves[1].append(d)
        elif dist <= 0.06:    # Wave 3 (~6km)
            waves[2].append(d)
        elif dist <= 0.08:    # Wave 4 (~8km)
            waves[3].append(d)
        elif dist <= 0.10:    # Wave 5 (~10km)
            waves[4].append(d)
            
    # Sort each wave natively by distance to ensure best in sub-group is first
    for wave in waves:
        wave.sort(key=lambda d: ((plat - d.location[0]) ** 2 + (plon - d.location[1]) ** 2) ** 0.5)
            
    return waves
