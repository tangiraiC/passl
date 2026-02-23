"""
Purpose: The batching “orchestrator” (single entry point).
What it does:

Coordinates the pipeline end-to-end:

- takes a set/list of candidate orders (from queue/batching_pool)

- clusters them (clustering.py)

- generates candidate bundles

- checks feasibility (feasibility.py) using OSRM times

- scores & selects (scoring.py)

- returns finalized Job objects + list of unbatched orders

Typical public function signature:

- batch_orders(orders: List[Order], osrm_client, policy) -> BatchResult
  where BatchResult contains:

- jobs: List[Job]

- unassigned_orders: List[Order]

- optional debug metrics

Rule: Engine is the only file other modules should call directly for batching.
"""

# orders/batching/engine.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from ..models import Job, Order
from .clustering import Cluster, build_clusters
from .feasibility import TimeMatrixProvider
from .policy import BatchingPolicy
from .scoring import score_and_select_jobs


@dataclass(frozen=True)
class BatchResult:
    """
    Output of a batching run for a set of candidate orders.
    """
    jobs: List[Job]
    unbatched_orders: List[Order]


def batch_orders(
    orders: Sequence[Order],
    *,
    policy: BatchingPolicy,
    # OSRM / routing adapters:
    stop_time_matrix_provider: TimeMatrixProvider,
    pickup_time_matrix_provider: Optional[TimeMatrixProvider] = None,
    # Optional: order_id -> age seconds for tie-breaks
    order_age_seconds: Optional[Dict[str, float]] = None,
) -> BatchResult:
    """
    Main batching entry point (pure algorithm).

    It does NOT mutate your queue. It only:
      - clusters candidate orders (same pickup_id, optionally near pickup)
      - scores and selects SINGLE/PAIR/TRIPLE jobs per cluster
      - returns jobs + any orders left unbatched (usually none unless you choose to hold them)

    Parameters
    ----------
    orders:
        Orders currently in your BATCHING pool (or the subset you want to process).
    policy:
        BatchingPolicy controlling detour caps, cluster limits, etc.
    stop_time_matrix_provider:
        OSRM time matrix provider for general stop-to-stop durations.
        Used for feasibility evaluation of 1-3 order bundles.
        Signature: (coords: List[LatLon]) -> matrix seconds.
    pickup_time_matrix_provider:
        Optional OSRM time matrix provider for pickup-to-pickup only,
        used in clustering for near-pickup merging.
        If omitted, clustering is primarily by pickup_id/coord buckets.
    order_age_seconds:
        Optional tie-breaker: order_id -> seconds in batching (or overall age).
        Used only if policy.prefer_older_orders is True.

    Returns
    -------
    BatchResult:
        jobs: list of finalized Job objects (SINGLE, BATCH_2, BATCH_3)
        unbatched_orders: orders that were not included in any job
    """
    policy.validate()

    if not orders:
        return BatchResult(jobs=[], unbatched_orders=[])

    # 1) Build clusters to reduce combinatorics and ensure logical grouping
    clusters: List[Cluster] = build_clusters(
        orders,
        policy,
        pickup_time_matrix_provider=pickup_time_matrix_provider,
    )

    jobs: List[Job] = []
    used_order_ids: set[str] = set()

    # 2) For each cluster, score & select disjoint jobs
    for cluster in clusters:
        if not cluster.orders:
            continue

        # Optional: if you want to avoid double-processing orders that appear in multiple clusters
        # (should be rare unless you enable near-pickup merging), skip already used orders.
        cluster_orders = [o for o in cluster.orders if o.id not in used_order_ids]
        if not cluster_orders:
            continue

        cluster_jobs = score_and_select_jobs(
            cluster_orders,
            time_matrix_provider=stop_time_matrix_provider,
            policy=policy,
            order_age_seconds=order_age_seconds,
        )

        # Track used orders
        for j in cluster_jobs:
            for oid in j.order_ids:
                used_order_ids.add(oid)

        jobs.extend(cluster_jobs)

    # 3) Determine unbatched orders (if any)
    by_id = {o.id: o for o in orders}
    unbatched = [by_id[oid] for oid in by_id.keys() if oid not in used_order_ids]

    return BatchResult(jobs=jobs, unbatched_orders=unbatched)