"""
Purpose: Core data models for the drivers domain.
What it does:
Defines the structure of a Driver and their status without relying on Django ORM constraints.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Tuple

LatLon = Tuple[float, float]


class DriverStatus(str, Enum):
    """
    Standardizes the state a driver can be in.
    Replaces the raw strings found in `dispatch.candidate_filter`.
    """
    AVAILABLE = "available"
    TRANSIT_TO_COLLECT = "transittoCollect"
    TRANSIT_TO_DROPOFF = "transittoDropoff"
    PAUSED = "paused"
    OFFLINE = "offline"
    UNREGISTERED = "unregistered"


@dataclass(frozen=True)
class Driver:
    """
    A purely stateless representation of a Driver at a specific point in time.
    """
    id: str
    location: LatLon
    status: DriverStatus
    
    # Optional constraints the dispatch engine can utilize.
    max_capacity: int = 3
    last_ping_at: datetime | None = None

    @classmethod
    def new(
        cls,
        driver_id: str,
        lat: float,
        lon: float,
        status: str | DriverStatus = DriverStatus.UNREGISTERED,
        max_capacity: int = 3,
        last_ping_at: datetime | None = None
    ) -> Driver:
        if isinstance(status, str):
            status = DriverStatus(status)
            
        return cls(
            id=driver_id,
            location=(lat, lon),
            status=status,
            max_capacity=max_capacity,
            last_ping_at=last_ping_at or datetime.now()
        )
