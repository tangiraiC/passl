# orders/batching/feasibility.py

from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from ..models import LatLon, Order, Stop, StopType


# ---- Types you plug into from routing/ (OSRM) ----
# Provide a function that returns an NxN duration matrix (seconds)
# for the given list of coordinates in the same order.
TimeMatrixProvider = Callable[[List[LatLon]], List[List[float]]]


@dataclass(frozen=True)
class FeasibilityResult:
    """
    Output of feasibility evaluation for a candidate bundle.
    """
    is_feasible: bool
    best_stops: List[Stop]
    best_time_seconds: float

    # Diagnostics (optional but useful)
    explored_sequences: int = 0
    reason: Optional[str] = None


def evaluate_bundle_feasibility(
    orders: Sequence[Order],
    time_matrix_provider: TimeMatrixProvider,
) -> FeasibilityResult:
    """
    Compute the best feasible stop sequence (min travel time) for a bundle of 1-3 orders.

    Feasibility constraint (precedence):
      For each order i: PICKUP(i) must occur before DROPOFF(i)

    Notes:
    - Works for identical OR different pickups.
    - Uses an OSRM table-style matrix provider to avoid repeated /route calls.
    - Intended for small bundles (<=3). For larger bundles you need heuristic search.
    """
    n = len(orders)
    if n <= 0:
        return FeasibilityResult(False, [], float("inf"), reason="empty bundle")
    if n > 3:
        return FeasibilityResult(False, [], float("inf"), reason="bundle size > 3 not supported")

    # Build stop list: 2 stops per order (pickup, dropoff)
    stops: List[Stop] = []
    for order in orders:
        stops.append(Stop(stop_type=StopType.PICKUP, order_id=order.id, coord=order.pickup, pickup_id=order.pickup_id))
        stops.append(Stop(stop_type=StopType.DROPOFF, order_id=order.id, coord=order.dropoff, pickup_id=order.pickup_id))

    # Map order_id -> indices of its pickup/dropoff stop in `stops`
    pickup_index: Dict[str, int] = {}
    dropoff_index: Dict[str, int] = {}
    for idx, stop in enumerate(stops):
        if stop.stop_type == StopType.PICKUP:
            pickup_index[stop.order_id] = idx
        else:
            dropoff_index[stop.order_id] = idx

    # Precompute OSRM durations between all stops
    coordinates = [stop.coord for stop in stops]
    durations = time_matrix_provider(coordinates)

    if not durations or len(durations) != len(coordinates):
        return FeasibilityResult(False, [], float("inf"), reason="invalid OSRM matrix (row count)")
    for row in durations:
        if len(row) != len(coordinates):
            return FeasibilityResult(False, [], float("inf"), reason="invalid OSRM matrix (col count)")

    # Enumerate valid sequences of stop indices with precedence constraints
    stop_indices = list(range(len(stops)))

    best_time = float("inf")
    best_perm: Optional[Tuple[int, ...]] = None
    explored = 0

    for perm in permutations(stop_indices):
        explored += 1
        if not _respects_precedence(perm, pickup_index, dropoff_index):
            continue

        t = _sequence_time_seconds(perm, durations)
        if t < best_time:
            best_time = t
            best_perm = perm

    if best_perm is None:
        return FeasibilityResult(False, [], float("inf"), explored_sequences=explored, reason="no feasible sequence")

    best_stops = [stops[i] for i in best_perm]
    return FeasibilityResult(True, best_stops, best_time, explored_sequences=explored)


def best_single_time_sum_seconds(
    orders: Sequence[Order],
    time_matrix_provider: TimeMatrixProvider,
) -> float:
    """
    Sum of individual (pickup -> dropoff) times for the given orders.
    This is used as the baseline for detour ratio:
      detour_ratio = t_batch / t_single_sum
    """
    if not orders:
        return 0.0

    # We only need pickup and dropoff coordinates for each order.
    # Build a small matrix over unique points to keep it efficient:
    # points = [P1, D1, P2, D2, ...]
    points: List[LatLon] = []
    idx_p: List[int] = []
    idx_d: List[int] = []

    for order in orders:
        idx_p.append(len(points))
        points.append(order.pickup)
        idx_d.append(len(points))
        points.append(order.dropoff)

    durations = time_matrix_provider(points)

    total = 0.0
    for pickup_idx, dropoff_idx in zip(idx_p, idx_d):
        total += float(durations[pickup_idx][dropoff_idx])

    return total


# -------------------------
# Internal helpers
# -------------------------

def _respects_precedence(
    perm: Tuple[int, ...],
    pickup_index: Dict[str, int],
    dropoff_index: Dict[str, int],
) -> bool:
    """
    Check precedence constraints under the permutation of stop indices.
    """
    pos = {stop_idx: i for i, stop_idx in enumerate(perm)}
    for order_id, pickup_idx in pickup_index.items():
        dropoff_idx = dropoff_index[order_id]
        if pos[pickup_idx] > pos[dropoff_idx]:
            return False
    return True


def _sequence_time_seconds(
    perm: Tuple[int, ...],
    durations: List[List[float]],
) -> float:
    """
    Sum durations for consecutive legs along the sequence.
    Starts at first stop (no prior location).
    """
    total = 0.0
    for a, b in zip(perm[:-1], perm[1:]):
        total += float(durations[a][b])
    return total

def evaluate_insertion(
    existing_stops: List[Stop],
    new_order: Order,
    time_matrix_provider: TimeMatrixProvider,
) -> FeasibilityResult:
    """
    Evaluates inserting a new_order (Pickup and Dropoff) into an existing sequence of stops.
    Tests all valid (P before D) insertion points into the existing_stops.
    Returns the best FeasibilityResult.
    """
    n = len(existing_stops)
    new_p_stop = Stop(stop_type=StopType.PICKUP, order_id=new_order.id, coord=new_order.pickup, pickup_id=new_order.pickup_id)
    new_d_stop = Stop(stop_type=StopType.DROPOFF, order_id=new_order.id, coord=new_order.dropoff, pickup_id=new_order.pickup_id)

    best_time = float("inf")
    best_stops = None
    explored = 0

    all_stops = list(existing_stops) + [new_p_stop, new_d_stop]
    unique_coordinates_map = {}
    coordinates = []
    for stop in all_stops:
        if stop.coord not in unique_coordinates_map:
            unique_coordinates_map[stop.coord] = len(coordinates)
            coordinates.append(stop.coord)

    durations = time_matrix_provider(coordinates)

    def sequence_time(seq: List[Stop]) -> float:
        total = 0.0
        for a, b in zip(seq[:-1], seq[1:]):
            a_idx = unique_coordinates_map[a.coord]
            b_idx = unique_coordinates_map[b.coord]
            total += float(durations[a_idx][b_idx])
        return total

    for i in range(n + 1):
        for j in range(i, n + 1):
            explored += 1
            seq = list(existing_stops)
            seq.insert(i, new_p_stop)
            seq.insert(j + 1, new_d_stop)

            t = sequence_time(seq)
            if t < best_time:
                best_time = t
                best_stops = seq

    if best_stops is None:
        return FeasibilityResult(False, [], float("inf"), explored_sequences=explored, reason="no feasible sequence")

    return FeasibilityResult(True, best_stops, best_time, explored_sequences=explored)