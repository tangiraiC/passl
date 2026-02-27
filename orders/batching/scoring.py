"""
Purpose: Rank feasible bundles and choose the best non-overlapping set.
What it does:

Computes for each candidate insertion:

t_single_sum = Σ time(Pi→Di)

detour_ratio = t_batch / t_single_sum

savings = t_single_sum - t_batch

optional aging penalty: prefer orders that have waited longer

Applies acceptance rules from policy:

pair pass if detour_ratio <= PAIR_DETOUR_CAP

multi pass if detour_ratio <= MULTI_DETOUR_CAP

Selects disjoint bundles using an Insertion Heuristic loop.

Outputs:

selected Job candidates (not yet committed to queue state)

Rule: Scoring chooses what to batch; it does not manage queues/state.
"""

# orders/batching/scoring.py

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from ..models import Job, JobType, Order, Stop, StopType
from .feasibility import (
    FeasibilityResult,
    TimeMatrixProvider,
    best_single_time_sum_seconds,
    evaluate_insertion,
)
from .policy import BatchingPolicy

def score_and_select_jobs(
    orders: Sequence[Order],
    time_matrix_provider: TimeMatrixProvider,
    policy: BatchingPolicy,
    *,
    order_age_seconds: Optional[Dict[str, float]] = None,
) -> List[Job]:
    """
    Score and select batches using an efficient Insertion Heuristic.

    Selection strategy:
      1) Pick an unbatched order to seed a new Job.
      2) While the job is under max_batch_size:
         Test inserting each remaining unbatched order.
         Add the order that provides the best incremental savings 
         while satisfying the detour caps.
      3) Repeat until all orders are grouped.

    Output:
      - list of Job objects
    """
    if not orders:
        return []

    unbatched = list(orders)
    jobs: List[Job] = []
    order_age_seconds = order_age_seconds or {}

    while unbatched:
        if policy.prefer_older_orders:
            unbatched.sort(key=lambda order: order_age_seconds.get(order.id, 0.0), reverse=True)
            
        seed_order = unbatched.pop(0)
        current_job_orders = [seed_order]
        
        current_stops = [
            Stop(stop_type=StopType.PICKUP, order_id=seed_order.id, coord=seed_order.pickup, pickup_id=seed_order.pickup_id),
            Stop(stop_type=StopType.DROPOFF, order_id=seed_order.id, coord=seed_order.dropoff, pickup_id=seed_order.pickup_id)
        ]
        
        current_single_sum = best_single_time_sum_seconds(current_job_orders, time_matrix_provider)
        current_batch_time = current_single_sum 
        
        while len(current_job_orders) < policy.max_batch_size and unbatched:
            best_gain = None
            best_order_to_insert = None
            best_insertion_result: Optional[FeasibilityResult] = None
            best_new_single_sum = 0.0
            
            for candidate in unbatched:
                feasibility_result = evaluate_insertion(current_stops, candidate, time_matrix_provider)
                if not feasibility_result.is_feasible:
                    continue
                    
                new_single_sum = current_single_sum + best_single_time_sum_seconds([candidate], time_matrix_provider)
                
                detour = feasibility_result.best_time_seconds / new_single_sum if new_single_sum > 0 else float("inf")
                
                # Check Detour Cap
                cap = policy.pair_detour_cap if len(current_job_orders) + 1 == 2 else policy.multi_detour_cap
                if detour > cap:
                    continue
                    
                savings = new_single_sum - feasibility_result.best_time_seconds
                score = float(savings)
                
                if policy.prefer_older_orders:
                    score += policy.age_weight * order_age_seconds.get(candidate.id, 0.0)
                
                baseline_savings = current_single_sum - current_batch_time 
                gain = score - baseline_savings
                
                if gain > 0 and (best_gain is None or gain > best_gain):
                    best_gain = gain
                    best_order_to_insert = candidate
                    best_insertion_result = feasibility_result
                    best_new_single_sum = new_single_sum
                    
            if best_order_to_insert is not None:
                current_job_orders.append(best_order_to_insert)
                unbatched.remove(best_order_to_insert)
                current_stops = best_insertion_result.best_stops
                current_batch_time = best_insertion_result.best_time_seconds
                current_single_sum = best_new_single_sum
            else:
                break
                
        if len(current_job_orders) == 1:
            age = order_age_seconds.get(seed_order.id, 0.0)
            if policy.enable_rolling_horizon and age < policy.max_wait_time_seconds:
                continue 
            jobs.append(_single_job(seed_order))
        else:
            job = Job.new(job_type=JobType.BATCH, order_ids=[order.id for order in current_job_orders], stops=current_stops)
            job.eta = current_batch_time
            job.detour_factor = current_batch_time / current_single_sum if current_single_sum > 0 else 1.0
            job.savings_percentage = current_single_sum - current_batch_time
            jobs.append(job)

    return jobs

def _single_job(order: Order) -> Job:
    stops = [
        Stop(stop_type=StopType.PICKUP, order_id=order.id, coord=order.pickup, pickup_id=order.pickup_id),
        Stop(stop_type=StopType.DROPOFF, order_id=order.id, coord=order.dropoff, pickup_id=order.pickup_id),
    ]
    job = Job.new(job_type=JobType.SINGLE, order_ids=[order.id], stops=stops)
    return job