# Orders Management & Batching Engine

This directory contains the core domain logic for managing logistics orders and the sophisticated algorithm responsible for batching them into optimized delivery jobs (Singles and dynamic Batches).

The system is designed to be **pure, stateless, and fully disconnected from Django/Celery state**. It relies exclusively on internal data models and pure math/routing constraints, allowing it to easily integrate with any queuing or execution system.

---

## 🏗️ 1. Domain Models (`models.py`)

The core entities that drive the batching system are heavily typed, dataclass-based models.

* **`Order`**: Represents a physical delivery request. Includes identifiers, `pickup` (lon, lat), `dropoff` (lon, lat), and `status`. Also tracks `created_at` utilizing timezone-aware datetime objects for measuring queue wait time.
* **`Job`**: The output unit of the batching engine. A `Job` is what gets dispatched to a driver. It has a `JobType` (SINGLE, BATCH), holds a list of `order_ids`, and strictly defines the exact sequence of `Stops`. It also outputs metrics like `eta`, `detour_factor`, and `savings_percentage` for tracking efficiency.
* **`Stop`**: Represents a single geographical waypoint in a job's routing sequence. It defines whether the stop is a `PICKUP` or `DROPOFF` for a given `order_id` at a specific `coord`.

---

## ⚙️ 2. The Batching Engine Architecture (`orders/batching/`)

The batching algorithm takes a flat list of `Order` objects and optimally reduces them into `Job` objects by leveraging OSRM (Open Source Routing Machine) travel-time matrices.

### The Pipeline (`engine.py`)
`engine.py` is the single external entry point (`batch_orders()`). It orchestrates a multi-step pipeline:
1. **Clustering** -> 2. **Candidate Generation** -> 3. **Feasibility Check** -> 4. **Scoring & Selection** -> 5. **Leftovers / Rolling Horizon**

### A. Clustering (`clustering.py`)
Comparing every order against every other order is $O(n^2)$. To scale, we cluster orders first.
* By default, the engine uses **Continuous Route Chaining** (`enable_continuous_chaining=True`), placing all orders under a global pool to allow mathematically finding dropoff-to-pickup chains across different merchants.
* When disabled, orders with identical `pickup_id` (e.g., the same restaurant) are put in the same cluster.
* Only orders within the same cluster are considered for batching together.

### B. Route Feasibility (`feasibility.py`)
Given a candidate insertion of an order into a route, the engine must find the optimal route.
* Rather than testing every single permutation mathematically, it tests all valid (Pickup before Dropoff) insertions into an already assembled `Stop` list.
* Uses the OSRM base Matrix Provider to score the total travel time of valid insertions.
* Returns a `FeasibilityResult` containing `is_feasible`, the `best_stops` sequence, and the lowest `best_time_seconds`.

### C. Scoring & Optimization (`scoring.py`)
After clustering unbatched orders, the system must build bundles.
* It uses a **Greedy Insertion Heuristic** loop, continually evaluating the best individual unbatched order to insert into a growing `Job` until it violates constraints.
* Calculates the **Detour Ratio** ($t_{batch} / \Sigma t_{single}$). To be valid, a bundle insertion must not exceed the `pair_detour_cap` or `multi_detour_cap`.
* Calculates **Savings**: $(\Sigma t_{single} - t_{batch})$.
* Sorts candidates greedily by maximum savings, repeatedly generating single or batched jobs up to `max_batch_size`.
* Handles unbatched "leftovers" (see Rolling Horizon below).

### D. Configuration & Tunings (`policy.py`)
`BatchingPolicy` holds all the configuration thresholds that dictate engine aggression. You can easily hot-swap policies dynamically (e.g., `default_policy()` vs `peak_policy()` vs `offpeak_policy()`) without changing the algorithmic math.
* `pair_detour_cap` and `multi_detour_cap`: Maximum acceptable detour ratio (e.g., `1.15`).
* `max_batch_size`: Max items in a job (dynamic, up to 10 or more).
* Time limits for age-based scoring tie-breaks.

### E. API Prefetching (Latency Mitigation)
To prevent the engine from making N OSRM queries for N permutations, `engine.py` supports bulk prefetching.
* Before scoring a cluster, the engine harvests all unique coordinates and injects them into the `time_matrix_provider.prefetch()` method.
* `PreloadingTimeMatrixProvider` inside `matrix_adapter.py` sends exactly **one** large `sources=all&destinations=all` query to OSRM.
* When `feasibility.py` actually requires times to test permutations, the provider bypasses the network and responds in 0.00ms from local RAM caches.

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
