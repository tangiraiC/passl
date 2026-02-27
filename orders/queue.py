"""
Purpose: Manages your 3-list lifecycle (RAW → BATCHING → READY).
What it does:
- Owns the in-memory or DB-backed queues/lists:
   - raw_orders
   - batching_pool
   - ready_jobs

Provides operations:
   - enqueue_raw(order)
   - move_to_batching(order_ids | criteria)
   - push_ready(job)
   - pop_ready(n)

Applies time/eligibility rules (not routing):
 - “when does an order leave RAW?”
 - “when do we finalize single if it waited too long?”

Calls batching engine at the right time (or exposes a method run_batching_cycle() that does).

Rule: Queue owns state transitions, batching owns optimization logic.
"""

from __future__ import annotations

from typing import List, Dict, Optional , Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from .models import Order, OrderStatus, JobType, Stop, StopType, Job
from .batching.policy import BatchingPolicy
from routing.matrix_adapter import TimeMatrixProvider

@dataclass
class QueueStats:
    raw_count: int
    batching_count: int
    ready_count: int
    now: datetime = field(default_factory=datetime.utcnow)

@dataclass
class OrdersQueue:
    """
    In-memory order lifecycle manager:

    RAW -> BATCHING -> READY (jobs)

    This owns state transitions and timing rules.
    Batching optimization logic lives elsewhere (orders/batching/engine.py).

    """
    #storage for orders in each state
    _orders:  Dict[str, Order] = field(default_factory=dict)  # all orders by id

    #stages are derived from all_orders_id
    _raw_ids: List[str] = field(default_factory=list)  # order ids in RAW
    _batching_ids: List[str] = field(default_factory=list)  # order ids in BATCHING
    _ready_jobs: List[any] = field(default_factory=list)  #

    #timestamps for stats and timing rules
    _entered_raw_at: Dict[str, datetime] = field(default_factory=dict)  # when each order entered RAW
    _entered_batching_at: Dict[str, datetime] = field(default_factory=dict)  # when each order entered BATCHING

    # --- Public API ---

    def enqueue_raw(self, order: Order) -> None:

        """ 
        Add a new order to the RAW queue.
        """
        now  = datetime.utcnow()
        if order.id in self._orders:
            #idempotency : dont double insert
            return
        order.status = OrderStatus.RAW
        self._orders[order.id] = order
        self._raw_ids.append(order.id)
        self._entered_raw_at[order.id] = now

    #get order metghod for internal use to avoid direct dict access 

    def get_order(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)
    
    def raw_orders(self) -> List[Order]:
        return [self._orders[order_id] for order_id in self._raw_ids]
    
    def batching_orders(self) -> List[Order]:
        return [self._orders[order_id] for order_id in self._batching_ids]
    
    def ready_jobs_list(self) -> List[any]:
        return list(self._ready_jobs)
    
    def pop_ready_jobs(self , num_jobs: int  = 1) -> List[any]:
        """
        FIFO POP FROM READY JOBS
        """

        if num_jobs <= 0: #n is the number of jobs to pop
            return []
        
        jobs = self._ready_jobs[:num_jobs]
        self._ready_jobs = self._ready_jobs[num_jobs:]
        return jobs
    
    def stats(self) -> QueueStats:
        return QueueStats(
            raw_count = len(self._raw_ids),
            batching_count = len(self._batching_ids),
            ready_count = len(self._ready_jobs),
            now= datetime.utcnow()
        )
    
    #---- Transition methods / helpers ----

    def move_raw_to_batching(self,*,
                            now: Optional[datetime] = None,
                            ready_horizon_secs: int = 0, # how long an order must wait in RAW before being eligible for batching   
                            max_raw_age_sec : Optional[int],
                            limit: Optional[int] = None,
                            ) -> List[Order]:
        """
        Move eligible orders from RAW -> BATCHING.

        Eligibility (simple + safe defaults):
        - If ready_horizon_sec == 0: move immediately.
        - Else: move when ready_at <= now + ready_horizon OR ready_at is None (unknown readiness).
        - Optional: max_raw_age_sec to prevent RAW stagnation (force move).
        - Optional: limit to bound per-cycle work.

        Returns the moved Order objects.

        """
        now = now or datetime.utcnow()
        moved :  List[Order] = []

        #iterate over a snapshot to allow removals 
        raw_snapshot = list(self._raw_ids)
        for order_id in raw_snapshot: 
            if limit is not None and len(moved) >= limit:
                break

            order = self._orders.get(order_id)
            if order.status != OrderStatus.RAW:
                #should not happen but skip if status changed
                self._raw_ids.remove(order_id)
                continue

            entered_raw_at = self._entered_raw_at.get(order_id, now)
            raw_age_sec = (now - entered_raw_at).total_seconds()

            force_by_age = ( #if max_raw_age_sec is set, force move if order has been in RAW too long
                max_raw_age_sec is not None and raw_age_sec >= max_raw_age_sec
            )

            ready_by_window= True #default to true if no horizon
            if ready_horizon_secs > 0:
                if order.ready_at is None:
                    # If you don't track readiness, treat as eligible.
                    ready_by_window = True
                else:
                    ready_by_window = order.ready_at <= (now + timedelta(seconds=ready_horizon_sec))

            if force_by_age or ready_by_window:
                self._raw_ids.remove(order_id)
                self._batching_ids.append(order_id)
                order.status = OrderStatus.BATCHING
                self._entered_batching_at[order_id] = now
                moved.append(order)

        return moved
    
    def finalize_orders_as_ready_jobs(
        self,
        jobs: List[Job],
        *,
        now: Optional[datetime] = None,
    ) -> None:
        """
        Commit batching results:
        - Push jobs to READY queue
        - Mark all included orders as READY and remove them from BATCHING list

        Assumes jobs only contain orders currently in BATCHING.
        """

        now = now or datetime.utcnow()

        # Build a set of all order_ids included in jobs
        used_order_ids = set()
        for job in jobs:
            for order_id in job.order_ids:
                used_order_ids.add(order_id)

        # Remove used orders from batching pool and update status
        # Iterate over a snapshot to safely remove
        batching_snapshot = list(self._batching_ids)
        for order_id in batching_snapshot:
            if order_id in used_order_ids:
                self._batching_ids.remove(order_id)
                order = self._orders.get(order_id)
                if order:
                    order.status = OrderStatus.READY

        # Append jobs FIFO
        self._ready_jobs.extend(jobs)

    def evict_cancelled(self, order_id: str) -> None:
        """
        Remove an order from any stage and mark cancelled.
        """
        order = self._orders.get(order_id)
        if not order:
            return

        order.status = OrderStatus.CANCELLED

        # Remove from lists if present
        if order_id in self._raw_ids:
            self._raw_ids.remove(order_id)
        if order_id in self._batching_ids:
            self._batching_ids.remove(order_id)

        # Keep record in _orders, or delete if you prefer:
        # del self._orders[order_id]

        self._entered_raw_at.pop(order_id, None)
        self._entered_batching_at.pop(order_id, None)

    # --- Timing utilities (useful for policy later) ---

    def batching_wait_seconds(self, order_id: str, now: Optional[datetime] = None) -> Optional[float]:
        """
        How long an order has been in BATCHING.
        """
        now = now or datetime.utcnow()
        t0 = self._entered_batching_at.get(order_id)
        if not t0:
            return None
        return (now - t0).total_seconds()

    def raw_wait_seconds(self, order_id: str, now: Optional[datetime] = None) -> Optional[float]:
        """
        How long an order has been in RAW.
        """
        now = now or datetime.utcnow()
        t0 = self._entered_raw_at.get(order_id)
        if not t0:
            return None
        return (now - t0).total_seconds()


class RollingHorizonManager:
    """
    The active time-based "Heartbeat" for the system.
    Simulates a background cron job loop.
    Reads waiting periods from the Queue, compares them against the Policy,
    and forces overdue orders into the Combinatorial Batching Engine.
    """
    def __init__(self, queue: OrdersQueue, policy: BatchingPolicy, stop_time_provider: TimeMatrixProvider):
        self.queue = queue
        self.policy = policy
        self.stop_time_provider = stop_time_provider
        
    def run_cycle(self, now: Optional[datetime] = None) -> List[Job]:
        """
        1. Grabs orders from RAW that have exceeded `batching_soft_wait_sec`.
        2. Funnels them into BATCHING.
        3. Fires up `orders.engine.batch_orders`.
        4. Saves returning Jobs into READY state to be caught by the 5-Wave Dispatcher.
        """
        now = now or datetime.utcnow()
        
        # 1. Promote ripe Orders from RAW to BATCHING based strictly on policy limits.
        self.queue.move_raw_to_batching(
            now=now,
            max_raw_age_sec=self.policy.batching_soft_wait_sec,
            limit=self.policy.max_cluster_candidates * 10 # Batch scaling safety
        )
        
        # 2. Extract exactly what is mathematically parked in the BATCHING stage
        batching_pool = self.queue.batching_orders()
        
        if not batching_pool:
            return [] # Nothing ripe to batch yet.
            
        # 3. Calculate exact age_weights so older orders out-compete newer orders
        order_age_seconds: Dict[str, float] = {}
        if self.policy.prefer_older_orders:
            for order in batching_pool:
                age = self.queue.batching_wait_seconds(order.id, now)
                # Fallback to pure age if they just transitioned
                if age is None or age == 0:
                    age = self.queue.raw_wait_seconds(order.id, now) or 1.0
                order_age_seconds[order.id] = age
                
        # 4. Fire the Orchestrator
        from .batching.engine import batch_orders
        
        result = batch_orders(
            orders=batching_pool,
            policy=self.policy,
            stop_time_matrix_provider=self.stop_time_provider,
            order_age_seconds=order_age_seconds
        )
        
        # 5. Lock resulting outputs directly into the READY queue.
        if result.jobs:
            self.queue.finalize_orders_as_ready_jobs(jobs=result.jobs, now=now)
            
        return result.jobs