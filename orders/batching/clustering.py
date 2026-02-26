"""
Purpose: Decide which orders are even allowed to be considered together.
What it does:

Groups the batching pool into clusters such as:

same pickup_id (primary)

optional “near pickup” clusters using OSRM pickup→pickup time or a geo prefilter

Outputs:

clusters: Dict[cluster_key, List[Order]]

Applies candidate caps:

keep only top K orders per cluster (e.g., oldest first) to prevent combinatorial explosion

Rule: Clustering does not score routes; it only forms candidate neighborhoods.
"""

# orders/batching/clustering.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from ..models import LatLon, Order
from .feasibility import TimeMatrixProvider
from .policy import BatchingPolicy


@dataclass(frozen=True)
class Cluster:
    """
    A cluster groups orders that are eligible to be considered together for batching.

    Typically:
      - same pickup_id (strongest grouping), and optionally
      - near pickups (different pickup_id but close in travel time)
    """
    key: str
    orders: List[Order]


def build_clusters(
    orders: Sequence[Order],
    policy: BatchingPolicy,
    *,
    pickup_time_matrix_provider: Optional[TimeMatrixProvider] = None,
) -> List[Cluster]:
    """
    Create batching clusters from a list of orders.

    Strategy:
      1) Group by pickup_id when pickup_id exists (hard grouping).
      2) Orders without pickup_id (or pickup_id=None) go into coordinate-based buckets.
      3) Optionally merge coordinate-based buckets that are "near" by OSRM pickup->pickup time.

    Inputs:
      - orders: typically the BATCHING pool (or a subset).
      - policy: controls max_cluster_candidates, near_pickup_time_sec, etc.
      - pickup_time_matrix_provider:
            If provided, it is used to evaluate "near pickup" merges across different pickup_ids.
            It must accept a list of pickup coordinates and return an NxN matrix of durations (seconds).
            If not provided, only exact pickup_id grouping is performed.

    Output:
      - list of Cluster objects (each cluster capped to policy.max_cluster_candidates)
    """
    if not orders:
        return []

    # 1) If continuous chaining is enabled, we bypass spatial partitions entirely.
    # The Insertion Heuristic in scoring will naturally reject combinations that violate Detour Caps 
    # and time matrices, meaning we don't need artificial boundaries.
    if getattr(policy, "enable_continuous_chaining", False):
         return [Cluster(key="global_chaining_pool", orders=list(orders))]

    # 2) Group by pickup_id (when available)
    by_pickup_id: Dict[str, List[Order]] = {}
    coord_bucket: List[Order] = []

    for o in orders:
        if o.pickup_id:
            by_pickup_id.setdefault(o.pickup_id, []).append(o)
        else:
            coord_bucket.append(o)

    clusters: List[Cluster] = []

    # Cap and sort inside each pickup_id cluster (older first is a good default)
    for pid, group in by_pickup_id.items():
        group_sorted = sorted(group, key=lambda x: x.created_at)
        clusters.append(Cluster(key=f"pickup_id:{pid}", orders=_cap(group_sorted, policy.max_cluster_candidates)))

    # 2) Coordinate-based fallback clusters (for orders without pickup_id)
    # We bucket by rounded coords to avoid making a separate cluster for every tiny coordinate variation.
    coord_clusters = _bucket_by_pickup_coord(coord_bucket)

    for key, group in coord_clusters.items():
        group_sorted = sorted(group, key=lambda x: x.created_at)
        clusters.append(Cluster(key=f"pickup_coord:{key}", orders=_cap(group_sorted, policy.max_cluster_candidates)))

    # 3) Optional near-pickup merge step (only for coordinate-based clusters).
    # For pickup_id clusters, we generally do NOT merge across pickup_ids by default because operationally
    # pickups at different merchants can have different readiness times and workflows.
    # If you want near-merchant merging, do it explicitly in a separate mode.
    if pickup_time_matrix_provider and policy.near_pickup_time_sec > 0:
        clusters = _merge_near_pickup_clusters(
            clusters=clusters,
            pickup_time_matrix_provider=pickup_time_matrix_provider,
            near_pickup_time_sec=policy.near_pickup_time_sec,
            max_cluster_candidates=policy.max_cluster_candidates,
        )

    return clusters


# -------------------------
# Internal helpers
# -------------------------

def _cap(items: List[Order], max_n: int) -> List[Order]:
    if max_n is None or max_n <= 0:
        return items
    return items[:max_n]


def _bucket_by_pickup_coord(orders: Sequence[Order], precision: int = 4) -> Dict[str, List[Order]]:
    """
    Bucket orders without pickup_id by rounded pickup coordinates.

    precision=4 -> ~11m precision on latitude (roughly), enough to group "same place" pickups.
    Adjust precision as needed.
    """
    buckets: Dict[str, List[Order]] = {}
    for o in orders:
        lat, lon = o.pickup
        key = f"{round(lat, precision)}:{round(lon, precision)}"
        buckets.setdefault(key, []).append(o)
    return buckets


def _merge_near_pickup_clusters(
    *,
    clusters: List[Cluster],
    pickup_time_matrix_provider: TimeMatrixProvider,
    near_pickup_time_sec: int,
    max_cluster_candidates: int,
) -> List[Cluster]:
    """
    Merge clusters whose representative pickups are close in OSRM travel time.

    Implementation notes:
    - We compute a pickup->pickup duration matrix for cluster representatives.
    - We union clusters that are mutually reachable within near_pickup_time_sec.
    - This is conservative and designed for small numbers of clusters.

    Representative pickup:
    - first order's pickup coord (after sorting) in each cluster.
    """
    if len(clusters) <= 1:
        return clusters

    # Build representative pickups
    reps: List[LatLon] = []
    for c in clusters:
        if not c.orders:
            reps.append((0.0, 0.0))
        else:
            reps.append(c.orders[0].pickup)

    durations = pickup_time_matrix_provider(reps)

    n = len(clusters)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    # Union near clusters
    for i in range(n):
        for j in range(i + 1, n):
            try:
                t_ij = float(durations[i][j])
                t_ji = float(durations[j][i])
            except Exception:
                continue

            # Consider near if either direction is within threshold
            if min(t_ij, t_ji) <= near_pickup_time_sec:
                union(i, j)

    # Group by root
    merged: Dict[int, List[Order]] = {}
    for idx, c in enumerate(clusters):
        r = find(idx)
        merged.setdefault(r, []).extend(c.orders)

    # Build output clusters, capped
    out: List[Cluster] = []
    for root, group in merged.items():
        # Create a stable key: merge:<root>
        group_sorted = sorted(group, key=lambda x: x.created_at)
        out.append(Cluster(key=f"merge:{root}", orders=_cap(group_sorted, max_cluster_candidates)))

    return out