# 🌅 Rolling Horizon Batching & Continuous Chaining: An Architectural Presentation

## Introduction: The Problems

1. **Immediate Dispatch Inefficiency**: In traditional routing, as soon as an order enters the system, a delivery driver is instantly dispatched to pick it up. This leads to poor efficiency during peak hours because you miss out on "batching" opportunities—matching two orders that are going in the same direction.
2. **Combinatorial Explosions**: If a system tries to batch large volumes, checking every mathematical combination of pickups and drop-offs to find the "best" route is computationally impossible for batch sizes greater than 3 ($O(N!)$).
3. **Strict Clustering**: Standard batching groups orders exclusively if they start at the exact same restaurant, missing out on "Chaining" opportunities (where dropping off Order A is right next to the pickup for Order B).

### The Solutions

Our new architecture fixes this with three core strategies:
1. **Rolling Horizon Batching**: Instead of immediate dispatch, the system holds onto a pool of young orders slightly longer (the "horizon"), continually evaluating them for optimal batches. If an order finds a good match, it gets batched. If an order ages past a maximum wait time, the horizon forces it to dispatch as a single order so that the customer's SLA is not violated.
2. **Greedy Insertion Heuristics**: To securely build dynamic batches of any size (up to 10 or more), the engine evaluates orders via O(N^2) insertions into a growing route rather than recalculating permutations from scratch.
3. **Continuous Route Chaining**: By dynamically merging orders into a global pool, the detours naturally find dropoff -> pickup overlaps across distinct merchants.

Here is how each file in the `orders` module interacts to achieve this.

---

## 🏗️ 1. `orders/models.py` (The State Keepers)
**Role:** Defines the raw data structures.

**Rolling Horizon Context:**
The rolling horizon requires tracking time perfectly. 
* `Order`: The core data structure includes a timezone-aware timestamp `created_at`.
* When the external system grabs `Order` objects from the database, it compares the current time to the `created_at` timestamp to determine the **Order Age in Seconds**. This age is the lifeblood of the rolling horizon logic.
* `JobType`: Supports purely `SINGLE` or dynamic `BATCH` payloads regardless of the number of stops.

---

## 🎛️ 2. `orders/batching/policy.py` (The Brain parameters)
**Role:** Defines all the mathematical thresholds and behavioral flags.

**Rolling Horizon & Chaining Context:**
Instead of hardcoding limits into the scoring logic, they are exposed here for easy tweaking:
* `enable_rolling_horizon: bool`: The master switch to turn deferred dispatching on or off.
* `max_wait_time_seconds: int`: The most critical parameter for the horizon. It defines how old an order must be before the system gives up trying to find a batch and forces it into a Single job.
* `enable_continuous_chaining: bool`: Swaps the engine from strict "same-restaurant-only" clustering to a dynamic global pooling strategy.
* `multi_detour_cap: float`: The absolute time cost limits assigned to any dynamic bundle built by the heuristic engine.

---

## 🚦 3. `orders/batching/engine.py` (The Orchestrator)
**Role:** The entry point `batch_orders()` that guides data through the steps.

**Orchestrator Context:**
* The orchestrator accepts an optional dictionary called `order_age_seconds: Dict[str, float]`. 
* This is where the external system (Celery/Django) tells the pure batching engine exactly how old each order is. 
* It manages bulk-prefetching from the OSRM time matrix cache, drastically speeding up HTTP routing requests, and passes data down the pipeline.

---

## 🔍 4. `orders/batching/clustering.py` (The Optimizer)
**Role:** Partitions candidate pools.

**Continuous Chaining Context:**
* Under standard rules, this groups orders that originate strictly from the same location to prune search spaces.
* With `enable_continuous_chaining` active, this module immediately returns the **global pool**. It throws all orders in the pipeline into one massive list; because the new heuristic engine is extremely fast, it trusts the OSRM detours to natively weed out logically separate regions without applying geographical fences beforehand.

---

## 🛣️ 5. `orders/batching/feasibility.py` (The Reality Checker)
**Role:** Asks OSRM exactly how much time an addition to a route will cost.

**Insertion Context:**
* Rather than recalculating $N!$ route permutations every time it checks 10 orders together, it utilizes `evaluate_insertion()`.
* It receives a fully optimized set of stops, and tests inserting a new `Pickup` and `Dropoff` exactly where they make the most mathematical sense. It simply returns the `FeasibilityResult` with the new sequence.

---

## ⚖️ 6. `orders/batching/scoring.py` (The Executioner)
**Role:** The core "Greedy Insertion Loop" that dynamically grows jobs.

**Horizon & Insertion Context:**
**This is where the rolling horizon physically executes.**
* The engine picks a seed order and dynamically tests inserting every unbatched order into it, permanently attaching the one that results in the highest positive savings vs a baseline detour.
* It loops this continuously until `max_batch_size` (e.g. 10) is hit or all valid mathematical options are exhausted.
* **The Horizon Check:** In a naive system, anything that couldn't batch cleanly drops into a `JobType.SINGLE` directly. But under the rolling horizon, the system checks the `order_age_seconds` variable for each single leftover.
* **Deferral (The Core Action):** 
  ```python
  if policy.enable_rolling_horizon and age < policy.max_wait_time_seconds:
      continue 
  ```
  If the leftover order is younger than `max_wait_time_seconds`, the engine *skips* creating a single job. The order gracefully falls out of the loop and lands in the `BatchResult.unbatched_orders` output array.
* Because it is returned in `unbatched_orders`, the external daemon knows not to dispatch it yet, and that order will stay in the pool to be re-evaluated against new incoming orders on the very next pass!
