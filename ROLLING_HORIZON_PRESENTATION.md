# 🌅 Rolling Horizon Batching: An Architectural Presentation

## Introduction: What is a Rolling Horizon?
In immediate dispatch routing, as soon as an order enters the system, a delivery driver is instantly dispatched to pick it up. This leads to poor efficiency during peak hours because you miss out on "batching" opportunities—matching two orders that are going in the same direction.

**Rolling Horizon Batching** fixes this. Instead of immediate dispatch, the system holds onto a pool of young orders slightly longer (the "horizon"). It continuously re-evaluates ("rolls" over) this pool every few seconds to find high-efficiency batches. If an order finds a good match, it gets batched. If an order ages past a maximum wait time without finding a match, the horizon forces it to dispatch as a single order so that the customer's SLA (Service Level Agreement) is not violated.

Here is how each file in the `orders` module interacts to achieve this rolling horizon.

---

## 🏗️ 1. `orders/models.py` (The State Keepers)
**Role:** Defines the raw data structures.
**Rolling Horizon Context:**
The rolling horizon requires tracking time perfectly. 
* `Order`: The core data structure includes a timezone-aware timestamp `created_at`.
* When the external system (like a Celery worker) grabs `Order` objects from the database, it compares the current time to the `created_at` timestamp to determine the **Order Age in Seconds**. This age is the lifeblood of the rolling horizon logic.

---

## 🎛️ 2. `orders/batching/policy.py` (The Brain parameters)
**Role:** Defines all the mathematical thresholds and behavioral flags.
**Rolling Horizon Context:**
Instead of hardcoding the rolling horizon parameters into the scoring logic, they are exposed here for easy tweaking:
* `enable_rolling_horizon: bool`: The master switch to turn deferred dispatching on or off.
* `max_wait_time_seconds: int`: The most critical parameter for the horizon. It defines how old an order must be before the system gives up trying to find a batch and forces it into a Single job. For example, if set to 180s, an order is "young" at 179s and will be deferred. At 180s, it becomes "old" and is dispatched alone.
* `batching_soft_wait_sec: int` & `batching_hard_wait_sec: int`: Additional time-based parameters that can optionally penalize or boost scores as an order ages within the window.

---

## 🚦 3. `orders/batching/engine.py` (The Orchestrator)
**Role:** The entry point `batch_orders()` that guides data through the steps.
**Rolling Horizon Context:**
* The orchestrator accepts an optional dictionary called `order_age_seconds: Dict[str, float]`. 
* This is where the external system (Celery/Django) tells the pure batching engine exactly how old each order is. 
* The engine then passes this dictionary strictly down to the `score_and_select_jobs` step. 
* *Note: The engine doesn't mutate or enforce the horizon itself, it simply acts as the conduit to pass the ages to the decision-maker.*

---

## 🔍 4. `orders/batching/clustering.py` (The Optimizer)
**Role:** Reduces the massive $O(n^2)$ search space by grouping orders that originate from the same location (or extremely close locations).
**Rolling Horizon Context:**
* **Indirect but Crucial:** The rolling horizon holds *more* orders in the system at once. More orders mean exponentially more possible pair combinations. If we didn't cluster orders tightly by `pickup_id` first, the rolling horizon would cause the feasibility matrix calculations to explode into millions of combinations and timeout. Clustering makes holding orders in a pool computationally survivable.

---

## 🛣️ 5. `orders/batching/feasibility.py` (The Reality Checker)
**Role:** Asks OSRM (or the Matrix adapter) if routing a specific pair of orders is physically possible and calculates the travel time.
**Rolling Horizon Context:**
* **Agnostic:** This is the only file that does *not* care about the rolling horizon. It only cares about pure physics and geography: "How many seconds does it take to drive from Pickup A to Dropoff B?" It simply returns the matrix math to the scorer.

---

## ⚖️ 6. `orders/batching/scoring.py` (The Executioner)
**Role:** Evaluates the savings of all feasible routes, picks the best ones greedily, and handles unbatched orders.
**Rolling Horizon Context:**
**This is where the rolling horizon physically executes.**
* The engine first greedily creates all the high-efficiency `BATCH_3` and `BATCH_2` jobs it can.
* Whatever orders could not find an efficient math are dumped into a list called `leftovers`.
* **The Horizon Check:** In a naive system, the engine would loop through the `leftovers` and instantly turn them all into `JobType.SINGLE`. But under the rolling horizon, the system checks the `order_age_seconds` dictionary for each single piece of leftovers.
* **Deferral (The Core Action):** 
  ```python
  if policy.enable_rolling_horizon and age < policy.max_wait_time_seconds:
      continue 
  ```
  If the order is younger than `max_wait_time_seconds`, the engine *skips* creating a job. The order gracefully falls out of the loop and lands in the `BatchResult.unbatched_orders` list.
* Because it is returned in `unbatched_orders`, the external daemon knows not to assign it yet, and that order will stay in the pool to be re-evaluated against new incoming orders on the very next pass!
