# Orders Management & Batching Engine

This directory contains the core domain logic for managing logistics orders and the sophisticated algorithm responsible for batching them into optimized delivery jobs (Singles, Pairs, and Triples).

The system is designed to be **pure, stateless, and fully disconnected from Django/Celery state**. It relies exclusively on internal data models and pure math/routing constraints, allowing it to easily integrate with any queuing or execution system.

---

## 🏗️ 1. Domain Models (`models.py`)

The core entities that drive the batching system are heavily typed, dataclass-based models.

* **`Order`**: Represents a physical delivery request. Includes identifiers, `pickup` (lon, lat), `dropoff` (lon, lat), and `status`. Also tracks `created_at` utilizing timezone-aware datetime objects for measuring queue wait time.
* **`Job`**: The output unit of the batching engine. A `Job` is what gets dispatched to a driver. It has a `JobType` (SINGLE, BATCH_2, BATCH_3), holds a list of `order_ids`, and strictly defines the exact sequence of `Stops`. It also outputs metrics like `eta`, `detour_factor`, and `savings_percentage` for tracking efficiency.
* **`Stop`**: Represents a single geographical waypoint in a job's routing sequence. It defines whether the stop is a `PICKUP` or `DROPOFF` for a given `order_id` at a specific `coord`.

---

## ⚙️ 2. The Batching Engine Architecture (`orders/batching/`)

The batching algorithm takes a flat list of `Order` objects and optimally reduces them into `Job` objects by leveraging OSRM (Open Source Routing Machine) travel-time matrices.

### The Pipeline (`engine.py`)
`engine.py` is the single external entry point (`batch_orders()`). It orchestrates a multi-step pipeline:
1. **Clustering** -> 2. **Candidate Generation** -> 3. **Feasibility Check** -> 4. **Scoring & Selection** -> 5. **Leftovers / Rolling Horizon**

### A. Clustering (`clustering.py`)
Comparing every order against every other order is $O(n^2)$. To scale, we cluster orders first.
* Orders with identical `pickup_id` (e.g., the same restaurant) are put in the same cluster.
* Optional functionality allows merging clusters that are within a short OSRM driving distance using a dedicated `pickup_time_matrix_provider`.
* Only orders within the same cluster are considered for batching together.

### B. Route Feasibility (`feasibility.py`)
Given a candidate pair or triple of orders, the engine must find the optimal route.
* Calculates all valid permutations of pickups and dropoffs (e.g., P1 -> P2 -> D1 -> D2).
* Eliminates invalid routes (a dropoff cannot happen before its pickup).
* Uses the OSRM base Matrix Provider to score the total travel time of valid routes.
* Returns a `FeasibilityResult` containing `is_feasible`, the `best_stops` sequence, and the lowest `best_time_seconds`.

### C. Scoring & Optimization (`scoring.py`)
After finding feasible bundles, the system must choose which ones to dispatch.
* Calculates the **Detour Ratio** ($t_{batch} / \Sigma t_{single}$). To be valid, a bundle must not exceed the `pair_detour_cap` or `triple_detour_cap`.
* Calculates **Savings**: $(\Sigma t_{single} - t_{batch})$.
* Sorts candidates greedily by maximum savings, generating disjoint sets of optimized BATCH_2 and BATCH_3 jobs.
* Handles unbatched "leftovers" (see Rolling Horizon below).

### D. Configuration & Tunings (`policy.py`)
`BatchingPolicy` holds all the configuration thresholds that dictate engine aggression. You can easily hot-swap policies dynamically (e.g., `default_policy()` vs `peak_policy()` vs `offpeak_policy()`) without changing the algorithmic math.
* `pair_detour_cap`: Maximum acceptable detour ratio (e.g., `1.15`).
* `max_batch_size`: Max items in a job (1, 2, or 3).
* Time limits for age-based scoring tie-breaks.

---

## ⏳ 3. Rolling Horizon (Deferred Dispatch)

To maximize batching opportunities rather than dispatching instantly, the algorithm implements a **Rolling Horizon** inside `scoring.py`.

#### How it works:
Instead of instantly converting any "leftover" unbatched orders into `JobType.SINGLE`s and dispatching them, the engine inspects how long the order has been waiting.
1. The orchestrator optionally passes a dictionary mapping `order_id` to its age in seconds (`order_age_seconds: Dict[str, float]`).
2. The `BatchingPolicy` defines `max_wait_time_seconds` (e.g., 180s/3 minutes) and `enable_rolling_horizon`.
3. If a leftover order's age is less than the max wait time, the engine **defers** it. It skips creating a job and places the order into `BatchResult.unbatched_orders`.
4. If an order's age exceeds the limit, it is finally wrapped into a `JobType.SINGLE` to guarantee SLA fulfillment.

This allows external queues (like Celery Beat running every 30s) to continuously pass the same pool of `unbatched_orders` back into the engine, giving those orders extra time to find a high-efficiency pair before they are forced out alone.

---

## 🧪 4. Testing & Data Strategy

The algorithm must be heavily tested using spatial coordinate data representing real traffic matrices.

**`tests/test_batching_with_real_osrm.py`**
* To prevent aggressive flakiness and timeout issues associated with remote public OSRM instances during continuous integration checks, the test suite uses a `MockOSRM` adapter perfectly mimicking the OSRM JSON response format but computing pure Manhattan times. 
* Orders are constructed natively `(lon, lat)`.

**Simulated Load Generation**
A script `generate_mock_data.py` at the root exists to heavily pound the clustering system. It outputs a CSV `raw_orders_generated.csv`.
* It forcefully localizes hundreds of orders to a handful of "Restaurant/Merchant" centroids to mimic extreme peak-traffic volume.
* It ensures dropoff coordinates vary continuously, providing rich variance for testing Detour Ratios dynamically.
