"""
Purpose: Domain models for the Orders capability.
What it does:
- Defines core data structures:
- Order (id, pickup coords, dropoff coords, pickup_id, timestamps, status)
- Job (job_id, job_type SINGLE/PAIR/TRIPLE, order_ids, stop_sequence, metrics)
- Stop (type PICKUP/DROPOFF, order_id, lat/lon)

Defines enums/constants:
- OrderStatus = RAW | BATCHING | READY | ASSIGNED | CANCELLED
- JobType = SINGLE | BATCH_2 | BATCH_3

Defines any model validation rules (if using Pydantic).

Rule: No OSRM calls, no batching logic. Models only.
"""
from __future__ import annotations

from dataclasses import dataclass,field 
from enum import Enum
from typing import List, Optional, Tuple
from datetime import datetime
import uuid

Latlon = Tuple[float, float]

class OrderStatus(Enum):
    RAW = "RAW"
    BATCHING = "BATCHING"
    READY = "READY"
    ASSIGNED = "ASSIGNED"
    CANCELLED = "CANCELLED"

class JobType(Enum):
    SINGLE = "SINGLE"
    BATCH_2 = "BATCH_2"
    BATCH_3 = "BATCH_3"     

class StopType(Enum):
    PICKUP = "PICKUP"
    DROPOFF = "DROPOFF"

@dataclass(frozen=True)
class Stop:
    """
    A stop in a job route . For precedence constraints:
    each order will have a PICKUP stop that must occur before its corresponding DROPOFF stop.
    """

    stop_type : StopType
    order_id : str
    coordinates : LatLon
    pickup_id : Optional[str] = None

@dataclass
class Order:
    """
    Represents a single order with pickup and dropoff details.
    """

    id: str
    pickup_coordinates: Latlon
    dropoff_coordinates: Latlon
    pickup_id: Optional[str] = None
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    ready_at: Optional[datetime] = None

    status : OrderStatus = OrderStatus.RAW


@dataclass
class Job:
    """
    Output of batching (what goes to READY queue for driver assignment).
    """
    job_id : str
    job_type : JobType
    order_ids : List[str]

    #stop sequence determined by feasibility search
    stops : List[Stop]

    #Metrics for monitoring/analytics(optional but useful for analytics)
    eta : Optional[float] = None  # Estimated time of arrival for the job
    detour_factor : Optional[float] = None  # Ratio of actual route distance to direct distance
    savings_percentage : Optional[float] = None  # Percentage of distance/time saved compared to separate trips

    created_at: datetime = field(default_factory=datetime.utcnow)

    @staticmethod # Factory method to create a Job from a list of Orders and a stop sequence
    def new(job_type: JobType, orders: List[Order], stop_sequence: List[Stop]) -> Job:
        #uuid for unique job id generation
        return Job(
            job_id=str(uuid.uuid4()),
            job_type=job_type,
            order_ids=[order.id for order in orders],
            stops=stop_sequence
        )

