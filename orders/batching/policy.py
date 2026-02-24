"""
Purpose: Central configuration for batching behavior (single source of truth).
What it does:

Stores all tunable thresholds/caps:

MAX_BATCH_SIZE = 3

PAIR_DETOUR_CAP = 1.15

TRIPLE_DETOUR_CAP = 1.20

NEAR_PICKUP_TIME_SEC = 180 (optional)

MAX_CLUSTER_CANDIDATES = 20

MAX_WAIT_BATCHING_SEC = 600 (optional)

Optionally defines a BatchingPolicy object so you can pass policy explicitly.

Rule: No logic here—just parameters so you can tune without rewriting code.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BatchingPolicy:
    """
    Central configuration for order batching.

    Keep all batching thresholds here so behavior can be tuned without
    touching batching logic (engine/feasibility/scoring).

    Notes:
    - 'detour caps' implement your "same direction" rule using OSRM:
        detour_ratio = t_batch / sum(t_single)
      Lower caps = stricter batching (fewer bundles).
    - 'near pickup' is used when pickups are not identical (optional).
    """

    # --- Batch size caps ---
    max_batch_size: int = 10

    # --- Candidate control (performance / scalability) ---
    # Limit how many orders per cluster the algorithm considers.
    # Keep smaller if you expect large pickup clusters.
    max_cluster_candidates: int = 20

    # How many candidate pairs to keep before selecting (optional guard).
    max_candidate_pairs: int = 300

    # --- Pickup clustering rules ---
    # If pickup_id matches, they are always in the same cluster.
    # If pickup_id differs, treat as "near pickup" only if OSRM travel time
    # between pickups is within this threshold.
    near_pickup_time_sec: int = 180  # 3 minutes

    # --- Continuous Route Chaining ---
    # Merge all orders into a single global pool to check distance mathematics across all pick-ups and drop-offs.
    enable_continuous_chaining: bool = True
    chaining_radius_sec: int = 400

    # --- Detour caps (direction/efficiency constraints) ---
    # Pair bundle must not exceed this multiple of sum of individual trips.
    pair_detour_cap: float = 1.15

    # Multi bundle (>2) must not exceed this multiple of sum of individual trips.
    multi_detour_cap: float = 1.25

    # --- Waiting / aging rules (queue layer may enforce, but policy lives here) ---
    # Soft wait: after this, prioritize forming something (even if not perfect).
    batching_soft_wait_sec: int = 180  # 3 minutes

    # Hard wait: after this, finalize as single if still unbatched.
    batching_hard_wait_sec: int = 600  # 10 minutes

    # --- Rolling Horizon ---
    # Defer singles from dispatching if they haven't waited this long.
    enable_rolling_horizon: bool = True
    max_wait_time_seconds: int = 180  # 3 minutes

    # --- Optional SLA guards (if you track deadlines) ---
    # If you later add promised delivery windows, you can enable these checks in feasibility/scoring.
    enforce_sla: bool = False

    # --- Tie-break preferences ---
    # If True: favor older orders slightly when scores are close.
    prefer_older_orders: bool = True

    # Weight applied to "age seconds" when adjusting score (tiny by default).
    # score = savings_seconds + age_weight * age_seconds
    age_weight: float = 0.05

    def validate(self) -> None:
        """
        Basic sanity checks. Call once at startup if you want.
        """
        if self.max_batch_size < 1:
            raise ValueError("max_batch_size must be >= 1")

        if self.pair_detour_cap < 1.0:
            raise ValueError("pair_detour_cap must be >= 1.0")

        if self.multi_detour_cap < 1.0:
            raise ValueError("multi_detour_cap must be >= 1.0")

        if self.near_pickup_time_sec <= 0:
            raise ValueError("near_pickup_time_sec must be > 0")

        if self.max_cluster_candidates <= 0:
            raise ValueError("max_cluster_candidates must be > 0")

        if self.max_candidate_pairs <= 0:
            raise ValueError("max_candidate_pairs must be > 0")

        if self.batching_soft_wait_sec < 0 or self.batching_hard_wait_sec < 0:
            raise ValueError("batching wait seconds must be >= 0")

        if self.batching_hard_wait_sec and self.batching_soft_wait_sec:
            if self.batching_hard_wait_sec < self.batching_soft_wait_sec:
                raise ValueError("hard_wait must be >= soft_wait")


def default_policy() -> BatchingPolicy:
    """
    Convenience factory for the default policy.
    """
    p = BatchingPolicy()
    p.validate()
    return p


def peak_policy() -> BatchingPolicy:
    """
    Example: more aggressive batching during peaks (lunch/dinner/weekends).
    You can wire this up later to a time-series monitor.
    """
    p = BatchingPolicy(
        near_pickup_time_sec=240,    # allow slightly wider pickup proximity
        enable_continuous_chaining=True,
        chaining_radius_sec=500,
        pair_detour_cap=1.18,
        multi_detour_cap=1.35,
        batching_soft_wait_sec=120,  # rebatch sooner
        batching_hard_wait_sec=540,  # keep hard wait reasonable
        age_weight=0.08,
    )
    p.validate()
    return p


def offpeak_policy() -> BatchingPolicy:
    """
    Example: less aggressive batching during off-peak to protect ETAs.
    """
    p = BatchingPolicy(
        near_pickup_time_sec=150,
        enable_continuous_chaining=False,
        chaining_radius_sec=180,
        pair_detour_cap=1.10,
        multi_detour_cap=1.18,
        batching_soft_wait_sec=90,
        batching_hard_wait_sec=420,
        age_weight=0.03,
    )
    p.validate()
    return p