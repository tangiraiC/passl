import pytest
import math
import random
from typing import List

from drivers.models import Driver, DriverStatus
from drivers.selection import build_driver_waves

def calculate_exact_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return math.sqrt((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2)

@pytest.fixture
def mock_pickup_location():
    # Example: Center of a city
    return (40.7128, -74.0060)

def test_build_driver_waves_distribution(mock_pickup_location):
    """
    Test that randomly scattered drivers are correctly bucketed
    into 5 concentric waves based on distance from pickup.
    """
    base_lat, base_lon = mock_pickup_location
    
    # Generate 100 fake drivers scattered radially around the pickup location
    drivers = []
    for i in range(100):
        # Generate varied distances between 0 and 0.12 degrees (slightly past wave 5)
        offset_lat = (random.random() - 0.5) * 0.24  
        offset_lon = (random.random() - 0.5) * 0.24
        
        status = DriverStatus.AVAILABLE if i % 10 != 0 else DriverStatus.OFFLINE
        
        driver = Driver.new(
            driver_id=f"driver_{i}",
            lat=base_lat + offset_lat,
            lon=base_lon + offset_lon,
            status=status,
            max_capacity=3
        )
        drivers.append(driver)
        
    # Execute the wave builder
    waves = build_driver_waves(pickup_location=mock_pickup_location, drivers=drivers, required_capacity=1)
    
    # 1. Assert we always get exactly 5 waves back
    assert len(waves) == 5
    
    # 2. Assert no offline drivers made it through the eligibility filter
    for wave in waves:
        for driver in wave:
            assert driver.status == DriverStatus.AVAILABLE
            
    # 3. Assert distance boundaries for each wave are strictly enforced
    for driver in waves[0]:
        dist = calculate_exact_distance(*mock_pickup_location, *driver.location)
        assert dist <= 0.02
        
    for driver in waves[1]:
        dist = calculate_exact_distance(*mock_pickup_location, *driver.location)
        assert 0.02 < dist <= 0.04
        
    for driver in waves[4]:
        dist = calculate_exact_distance(*mock_pickup_location, *driver.location)
        assert 0.08 < dist <= 0.10

def test_build_driver_waves_sorting(mock_pickup_location):
    """
    Test that within a single wave array, the drivers are strictly
    sorted from mathematically closest to farthest.
    """
    base_lat, base_lon = mock_pickup_location
    
    drivers = [
        Driver.new("driver_far", base_lat + 0.015, base_lon + 0.015, DriverStatus.AVAILABLE),     # dist ~0.021 (Wave 2)
        Driver.new("driver_closest", base_lat + 0.001, base_lon + 0.001, DriverStatus.AVAILABLE), # dist ~0.001 (Wave 1)
        Driver.new("driver_close", base_lat + 0.01, base_lon + 0.01, DriverStatus.AVAILABLE),     # dist ~0.014 (Wave 1)
    ]
    
    waves = build_driver_waves(pickup_location=mock_pickup_location, drivers=drivers)
    
    # Assert Wave 1 sorting
    wave_1 = waves[0]
    assert len(wave_1) == 2
    assert wave_1[0].id == "driver_closest" # Must be index 0
    assert wave_1[1].id == "driver_close"
    
    # Assert Wave 2 distribution
    wave_2 = waves[1]
    assert len(wave_2) == 1
    assert wave_2[0].id == "driver_far"
