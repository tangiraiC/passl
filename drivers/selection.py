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

def find_best_driver(
    pickup_location: Tuple[float, float], 
    drivers: List[Driver], 
    required_capacity: int = 1,
    max_distance_degrees: float = 0.05  # roughly ~5km depending on lat
) -> Optional[Driver]:
    """
    Given a pickup location and a list of all system drivers,
    filter out ineligible ones and return the single closest driver
    using a fast Haversine/Euclidean approximation.
    
    If OSRM is needed for exact ETA, it can be passed in here later.
    """
    
    eligible = filter_eligible_drivers(drivers, required_capacity)
    if not eligible:
        return None
        
    best_driver = None
    best_distance = float('inf')
    
    plat, plon = pickup_location
    
    for d in eligible:
        dlat, dlon = d.location
        
        # Fast pythagorean distance approximation for initial filtering
        # In production, replace with Haversine or exact OSRM `table` calls
        dist = ((plat - dlat) ** 2 + (plon - dlon) ** 2) ** 0.5
        
        if dist > max_distance_degrees:
            continue
            
        if dist < best_distance:
            best_distance = dist
            best_driver = d
            
    return best_driver
