"""
Purpose: Central configuration for Driver Selection and Broadcast Waves.
What it does:

Stores all tunable thresholds/caps for finding drivers and pushing offers:

WAVE_TIMEOUT_SECONDS = 30
WAVE_RADII_DEGREES = [0.02, 0.04, 0.06, 0.08, 0.10]

Rule: No logic here—just parameters so you can tune without rewriting code.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List

@dataclass(frozen=True)
class DriverPolicy:
    """
    Central configuration for driver routing and dispatch thresholds.
    """
    
    # --- Dispatcher Timeout ---
    # How long to wait for a driver in a specific Wave to accept 
    # the push notification before broadening the radius to Wave N+1.
    wave_timeout_seconds: int = 30
    
    # --- Geofencing Rings ---
    # Used if falling back to Cartesian distance degrees when OSRM is offline.
    # Defines the concentric radii for Waves 1 through 5.
    # 0.02 roughly equals ~2.2 kilometers
    wave_radii_degrees: List[float] = field(default_factory=lambda: [0.02, 0.04, 0.06, 0.08, 0.10])
    
    # Accurate driving times in seconds (e.g., 3 mins, 7 mins, 10 mins...)
    # Only enforced if a PreloadingTimeMatrixProvider is injected into Dispatcher.
    wave_eta_seconds: List[int] = field(default_factory=lambda: [180, 420, 600, 780, 960])
    
    # --- Capacity Constraints ---
    # Default required capacity if a Job somehow fails to specify it
    default_required_capacity: int = 1

    def validate(self) -> None:
        """
        Basic sanity checks.
        """
        if self.wave_timeout_seconds <= 0:
            raise ValueError("wave_timeout_seconds must be > 0")

        if not self.wave_radii_degrees or len(self.wave_radii_degrees) != 5:
            raise ValueError("Must provide exactly 5 wave radii for the 5-Wave Dispatcher.")
            
        if not self.wave_eta_seconds or len(self.wave_eta_seconds) != 5:
            raise ValueError("Must provide exactly 5 wave ETAs in seconds.")

def default_driver_policy() -> DriverPolicy:
    """
    Convenience factory for the default policy.
    """
    p = DriverPolicy()
    p.validate()
    return p
