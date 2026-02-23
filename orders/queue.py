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

from .models import Order, OrderStatus, JobType, Stop, StopType

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
    all_orders_id:  Dict[str, Order] = field(default_factory=dict)  # all orders by id

    #stages are derived from all_orders_id
    raw_orders_ids: List[str] = field(default_factory=list)  # order ids in RAW
    batching_pool_ids: List[str] = field(default_factory=list)  # order ids in BATCHING
    ready_jobs: List[List[str]] = field(default_factory=list)  #

    #timestamps for stats and timing rules
    entered_raw_at: Dict[str, datetime] = field(default_factory=dict)  # when each order entered RAW
    entered_batching_at: Dict[str, datetime] = field(default_factory=dict)  # when each order entered BATCHING

    # --- Public API ---

    def enqueue_raw(self, order: Order) -> None:

        """ 
        Add a new order to the RAW queue.
        """
        now  = datetime.utcnow()
        if order.id in self.all_orders_id:
            #idempotency : dont double insert
            return
        order.status = OrderStatus.RAW
        self.orders(order.id) = order
        self.raw_orders_ids.append(order.id)
        self.entered_raw_at[order.id] = now

    #get order metghod for internal use to avoid direct dict access 

    def get_order(self, order_id: str) -> Optional[Order]:
        return self.orders.get(order_id)
    
    def raw_orders(self) -> List[Order]:
        return [self.orders[oid] for oid in self.raw_orders_ids]
    
    def batching_orders(self) -> List[Order]:
        return [self.orders[oid] for oid in self.batching_pool_ids]
    
    def ready_jobs_list(self) -> List[List[str]]:
        return list(self.ready_jobs)
    
    def pop_ready_jobs(self , n: int  = 1)->List[job]:
        """
        FIFO POP FROM READY JOBS
        """

        if n <= 0:
            return []
        
        jobs = self.ready_jobs[:n]
        self.ready_jobs = self.ready_jobs[n:]
        return jobs
    
    def stats(self) -> QueueStats:
        return QueueStats(
            raw_count = len(self.raw_orders_ids),
            batching_count = len(self.batching_pool_ids),
            ready_count = len(self.ready_jobs),
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
        raw_snapshot = list(self.raw_orders_ids)
        for oid in raw_snapshot: #oid is order id
            if limit is not None and len(moved) >= limit:
                break

            order = self.all_orders_id.get(oid)
            if order.status != OrderStatus.RAW:
                #should not happen but skip if status changed
                self.raw_orders_ids.remove(oid)
                continue

            entered_raw_at = self.entered_raw_at.get(oid, now)
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
                self._raw_ids.remove(oid)
                self._batching_ids.append(oid)
                order.status = OrderStatus.BATCHING
                self._entered_batching_at[oid] = now
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
            for oid in job.order_ids:
                used_order_ids.add(oid)

        # Remove used orders from batching pool and update status
        # Iterate over a snapshot to safely remove
        batching_snapshot = list(self._batching_ids)
        for oid in batching_snapshot:
            if oid in used_order_ids:
                self._batching_ids.remove(oid)
                order = self._orders.get(oid)
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





            