"""
Purpose: Rank feasible bundles and choose the best non-overlapping set.
What it does:

Computes for each candidate bundle:

t_single_sum = Σ time(Pi→Di)

detour_ratio = t_batch / t_single_sum

savings = t_single_sum - t_batch

optional aging penalty: prefer orders that have waited longer

Applies acceptance rules from policy:

pair pass if detour_ratio <= PAIR_DETOUR_CAP

triple pass if detour_ratio <= TRIPLE_DETOUR_CAP

Selects disjoint bundles:

start with best pairs (greedy max savings or matching)

attempt triple upgrade (pair + best third) if it improves and remains feasible

Outputs:

selected Job candidates (not yet committed to queue state)

Rule: Scoring chooses what to batch; it does not manage queues/state.
"""

# orders/batching/scoring.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

from ..models import Job, JobType, Order, Stop, StopType
from .feasibility import (
    FeasibilityResult,
    TimeMatrixProvider,
    best_single_time_sum_seconds,
    evaluate_bundle_feasibility,
)
from .policy import BatchingPolicy


@dataclass(frozen=True)
class CandidateBundle:
    """
    A candidate bundle (size 1/2/3) with computed metrics.
    """
    order_ids: Tuple[str, ...]
    stops: List[Stop]
    batch_time_seconds: float
    single_time_sum_seconds: float
    detour_ratio: float
    savings_seconds: float
    score: float


def score_and_select_jobs(
    orders: Sequence[Order],
    time_matrix_provider: TimeMatrixProvider,
    policy: BatchingPolicy,
    *,
    order_age_seconds: Optional[Dict[str, float]] = None,
) -> List[Job]:
    """
    Score bundles (pairs + optional triples) and select a disjoint set of jobs.

    Selection strategy:
      1) Build feasible PAIRS with detour caps.
      2) Select disjoint best pairs (greedy by score).
      3) Try upgrading selected pairs to TRIPLES by adding one leftover order if it improves and passes caps.
      4) Any leftover orders become SINGLE jobs.

    Inputs:
      - orders: typically a cluster (same/near pickup), already capped in size.
      - time_matrix_provider: OSRM table-duration provider (seconds).
      - policy: detour caps, limits, preferences.
      - order_age_seconds: optional mapping order_id -> age seconds in batching,
        used only as a small tie-breaker (if enabled in policy).

    Output:
      - list of Job objects (SINGLE, BATCH_2, BATCH_3)
    """
    if not orders:
        return []

    # Index orders by id for quick access
    by_id: Dict[str, Order] = {o.id: o for o in orders}
    order_ids = list(by_id.keys())

    # 1) Build candidate pairs
    pair_candidates = _build_pair_candidates(
        orders=orders,
        time_matrix_provider=time_matrix_provider,
        policy=policy,
        order_age_seconds=order_age_seconds,
    )

    # 2) Select disjoint best pairs (greedy)
    selected_pairs: List[CandidateBundle] = _select_disjoint_greedy(pair_candidates)

    used: Set[str] = set()
    for c in selected_pairs:
        used.update(c.order_ids)

    leftovers = [by_id[oid] for oid in order_ids if oid not in used]

    # 3) Upgrade to triples (optional)
    selected_triples: List[CandidateBundle] = []
    if policy.allow_triples and policy.max_batch_size >= 3 and leftovers:
        selected_triples, selected_pairs, leftovers = _upgrade_pairs_to_triples(
            selected_pairs=selected_pairs,
            leftovers=leftovers,
            time_matrix_provider=time_matrix_provider,
            policy=policy,
            order_age_seconds=order_age_seconds,
        )

    # 4) Convert to jobs + singles
    jobs: List[Job] = []
    for c in selected_triples:
        jobs.append(_candidate_to_job(c, JobType.BATCH_3))
    for c in selected_pairs:
        jobs.append(_candidate_to_job(c, JobType.BATCH_2))
    for o in leftovers:
        # Check rolling horizon: defer if young
        age = order_age_seconds.get(o.id, 0.0) if order_age_seconds else 0.0
        
        if policy.enable_rolling_horizon and age < policy.max_wait_time_seconds:
            # DEFER: Do not create a job. 
            continue 
            
        jobs.append(_single_job(o))

    return jobs


# -------------------------
# Candidate construction
# -------------------------

def _build_pair_candidates(
    *,
    orders: Sequence[Order],
    time_matrix_provider: TimeMatrixProvider,
    policy: BatchingPolicy,
    order_age_seconds: Optional[Dict[str, float]],
) -> List[CandidateBundle]:
    """
    Build feasible pair candidates and compute scores.
    """
    ids = [o.id for o in orders]
    by_id = {o.id: o for o in orders}

    candidates: List[CandidateBundle] = []

    # Generate all pairs (i < j)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            o1 = by_id[ids[i]]
            o2 = by_id[ids[j]]

            # Compute feasibility and best route time for the bundle
            feas: FeasibilityResult = evaluate_bundle_feasibility(
                [o1, o2],
                time_matrix_provider=time_matrix_provider,
            )
            if not feas.is_feasible:
                continue

            single_sum = best_single_time_sum_seconds(
                [o1, o2],
                time_matrix_provider=time_matrix_provider,
            )
            if single_sum <= 0:
                continue

            detour = feas.best_time_seconds / single_sum
            
            print(
                "PAIR DEBUG",
                o1.id, o2.id,
                "batch_time", feas.best_time_seconds,
                "single_sum", single_sum,
                "ratio", feas.best_time_seconds / single_sum
            )

            if detour > policy.pair_detour_cap:
                continue

            savings = single_sum - feas.best_time_seconds

            # Score: savings + (optional) slight preference for older orders
            score = float(savings)
            if policy.prefer_older_orders and order_age_seconds:
                age = float(order_age_seconds.get(o1.id, 0.0) + order_age_seconds.get(o2.id, 0.0))
                score += policy.age_weight * age

            candidates.append(
                CandidateBundle(
                    order_ids=tuple(sorted((o1.id, o2.id))),
                    stops=feas.best_stops,
                    batch_time_seconds=float(feas.best_time_seconds),
                    single_time_sum_seconds=float(single_sum),
                    detour_ratio=float(detour),
                    savings_seconds=float(savings),
                    score=float(score),
                )
            )

            # Guard rail: cap number of candidate pairs if desired
            if len(candidates) >= policy.max_candidate_pairs:
                break
        if len(candidates) >= policy.max_candidate_pairs:
            break

    # Sort descending by score (greedy selection uses this ordering)
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates


def _upgrade_pairs_to_triples(
    *,
    selected_pairs: List[CandidateBundle],
    leftovers: List[Order],
    time_matrix_provider: TimeMatrixProvider,
    policy: BatchingPolicy,
    order_age_seconds: Optional[Dict[str, float]],
) -> Tuple[List[CandidateBundle], List[CandidateBundle], List[Order]]:
    """
    Attempt to upgrade selected disjoint pairs into triples by adding one leftover order.

    Strategy:
      - For each selected pair, find the best third order from leftovers that:
         a) yields a feasible triple
         b) passes triple detour cap
         c) provides positive incremental improvement (score)
      - Apply upgrades greedily by best incremental gain, ensuring a leftover order is not reused.
    """
    if not selected_pairs or not leftovers:
        return [], selected_pairs, leftovers

    # Index leftovers for quick access
    leftover_by_id: Dict[str, Order] = {o.id: o for o in leftovers}

    upgrade_options: List[Tuple[float, CandidateBundle, CandidateBundle, str]] = []
    # tuple: (gain, triple_candidate, original_pair, added_order_id)

    # Precompute single times for leftover as needed is handled by best_single_time_sum_seconds calls.

    for pair in selected_pairs:
        o1_id, o2_id = pair.order_ids
        # We'll need the actual Order objects for feasibility eval
        # (We cannot assume we have them here, so we infer from stops? Better: just store them outside.)
        # For now, we reconstruct orders from leftovers + selected pair isn't in leftovers.
        # We'll pass orders explicitly by ids by requiring caller to use cluster-level by_id if needed.
        # To keep scoring.py self-contained, we infer Orders from stops is not safe.
        # Instead, we encode in stops? No. So we'll compute triples using ids only if we have access.
        #
        # Solution: require that leftover candidates only add to pair by evaluating feasibility using coords from stops:
        # But stops include pickup/dropoff coords per order, so we can rebuild minimal Order objects from stops.
        #
        # We'll rebuild minimal Orders for o1,o2 based on best_stops:
        o1, o2 = _rebuild_orders_from_stops(pair.stops, o1_id, o2_id)

        best_gain = None
        best_triple = None
        best_added_id = None

        for add in leftovers:
            feas = evaluate_bundle_feasibility([o1, o2, add], time_matrix_provider=time_matrix_provider)
            if not feas.is_feasible:
                continue

            single_sum = best_single_time_sum_seconds([o1, o2, add], time_matrix_provider=time_matrix_provider)
            if single_sum <= 0:
                continue

            detour = feas.best_time_seconds / single_sum
            if detour > policy.triple_detour_cap:
                continue

            savings = single_sum - feas.best_time_seconds

            # Compute triple score
            score = float(savings)
            if policy.prefer_older_orders and order_age_seconds:
                age = float(
                    order_age_seconds.get(o1.id, 0.0)
                    + order_age_seconds.get(o2.id, 0.0)
                    + order_age_seconds.get(add.id, 0.0)
                )
                score += policy.age_weight * age

            triple_candidate = CandidateBundle(
                order_ids=tuple(sorted((o1.id, o2.id, add.id))),
                stops=feas.best_stops,
                batch_time_seconds=float(feas.best_time_seconds),
                single_time_sum_seconds=float(single_sum),
                detour_ratio=float(detour),
                savings_seconds=float(savings),
                score=float(score),
            )

            # Incremental gain vs keeping the pair + leaving 'add' as single
            # single(add) baseline:
            single_add = best_single_time_sum_seconds([add], time_matrix_provider=time_matrix_provider)
            baseline = pair.savings_seconds + 0.0  # pair already accounts savings vs singles for its two
            gain = triple_candidate.savings_seconds - baseline

            # If triple doesn't actually improve compared to keeping pair, skip
            # (You can relax this if you value fewer jobs even without time savings.)
            if gain <= 0:
                continue

            if best_gain is None or gain > best_gain:
                best_gain = gain
                best_triple = triple_candidate
                best_added_id = add.id

        if best_triple and best_gain is not None and best_added_id:
            upgrade_options.append((best_gain, best_triple, pair, best_added_id))

    # Apply upgrades greedily by best gain, ensure we don't reuse leftover orders
    upgrade_options.sort(key=lambda x: x[0], reverse=True)

    used_leftover: Set[str] = set()
    triples: List[CandidateBundle] = []
    remaining_pairs: List[CandidateBundle] = []

    upgraded_pair_ids: Set[Tuple[str, ...]] = set()

    for gain, triple_cand, original_pair, added_id in upgrade_options:
        if added_id in used_leftover:
            continue
        if original_pair.order_ids in upgraded_pair_ids:
            continue

        triples.append(triple_cand)
        used_leftover.add(added_id)
        upgraded_pair_ids.add(original_pair.order_ids)

    # Keep pairs that weren't upgraded
    for pair in selected_pairs:
        if pair.order_ids not in upgraded_pair_ids:
            remaining_pairs.append(pair)

    # Remove used leftovers
    new_leftovers = [o for o in leftovers if o.id not in used_leftover]

    return triples, remaining_pairs, new_leftovers


def _select_disjoint_greedy(candidates: List[CandidateBundle]) -> List[CandidateBundle]:
    """
    Greedy selection of non-overlapping bundles by descending score.
    """
    selected: List[CandidateBundle] = []
    used: Set[str] = set()

    for c in candidates:
        if any(oid in used for oid in c.order_ids):
            continue
        selected.append(c)
        used.update(c.order_ids)

    return selected


# -------------------------
# Job conversion helpers
# -------------------------

def _candidate_to_job(candidate: CandidateBundle, job_type: JobType) -> Job:
    job = Job.new(job_type=job_type, order_ids=list(candidate.order_ids), stops=candidate.stops)
    job.eta = candidate.batch_time_seconds
    job.detour_factor = candidate.detour_ratio
    job.savings_percentage = candidate.savings_seconds
    return job


def _single_job(order: Order) -> Job:
    stops = [
        Stop(stop_type=StopType.PICKUP, order_id=order.id, coord=order.pickup, pickup_id=order.pickup_id),
        Stop(stop_type=StopType.DROPOFF, order_id=order.id, coord=order.dropoff, pickup_id=order.pickup_id),
    ]
    job = Job.new(job_type=JobType.SINGLE, order_ids=[order.id], stops=stops)
    # eta_seconds can be filled later by assignment/routing step if needed
    return job


def _rebuild_orders_from_stops(stops: List[Stop], o1_id: str, o2_id: str) -> Tuple[Order, Order]:
    """
    Rebuild minimal Order objects from a candidate's stop list.

    This keeps scoring self-contained without requiring the caller to pass
    the cluster by_id mapping down into upgrade logic.

    Assumes stop list contains pickup+dropoff for each order_id.
    """
    def find_coords(oid: str) -> Tuple[Tuple[float, float], Tuple[float, float], Optional[str]]:
        p = None
        d = None
        pid = None
        for s in stops:
            if s.order_id != oid:
                continue
            pid = s.pickup_id
            if s.stop_type == StopType.PICKUP:
                p = s.coord
            elif s.stop_type == StopType.DROPOFF:
                d = s.coord
        if p is None or d is None:
            raise ValueError(f"Cannot rebuild Order {oid}: missing pickup/dropoff in stops")
        return p, d, pid

    p1, d1, pid1 = find_coords(o1_id)
    p2, d2, pid2 = find_coords(o2_id)

    return (
        Order(id=o1_id, pickup=p1, dropoff=d1, pickup_id=pid1),
        Order(id=o2_id, pickup=p2, dropoff=d2, pickup_id=pid2),
    )