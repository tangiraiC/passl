# PassL: API & Database Integration Guide

The core `passL` architecture is built entirely of **Pure Python Dataclasses and Algorithms**. It does not care where the data comes from (CSV, PostgreSQL, Redis, or API JSON). This makes the math incredibly fast and easy to test.

However, to use this in production, you must build the "Interface Layer"—the API endpoints and Database ORMs that translate the real world into the pure objects the algorithm expects.

Here is exactly what you need to build in Django, FastAPI, or Node.js to bridge the gap.

---

## 1. Entering The System (The Order Webhook)

Your merchant tablet (or consumer app) will send a JSON payload whenever a new food order is placed. You need a standard REST endpoint to catch it, save it to the database, and inject it into the algorithms.

### Endpoint: `POST /api/orders/webhook`

**The Incoming Payload:**
```json
{
  "order_id": "ORD-7742",
  "restaurant_id": "REST-99",
  "pickup_lat": -17.824858,
  "pickup_lon": 31.053028,
  "dropoff_lat": -17.8105,
  "dropoff_lon": 31.0772,
  "created_at": "2026-02-24T14:15:00Z"
}
```

**The Database Integration (Django ORM Example):**
When your controller receives this payload, you must persist it to the database, and then convert it into the pure algorithmic `passL.orders.models.Order` dataclass.

```python
# 1. Save to Postgres via your Web Framework
db_order = DatabaseOrder.objects.create(
    id=payload["order_id"],
    pickup_lat=payload["pickup_lat"],
    pickup_lon=payload["pickup_lon"],
    status="RAW"
)

# 2. Convert to the internal Dataclass
pure_order = Order(
    id=db_order.id,
    pickup=(db_order.pickup_lat, db_order.pickup_lon),
    dropoff=(db_order.dropoff_lat, db_order.dropoff_lon),
    pickup_id=payload["restaurant_id"]
)

# 3. Inject it into the Rolling Horizon Queue
rolling_horizon_manager.queue.enqueue_raw(pure_order)
```

---

## 2. The Heartbeat (Triggering the Dispatcher)

The algorithms do not run themselves. You need a background worker (like **Celery**, **Redis Queue**, or a simple `asyncio` loop) to repeatedly execute the `RollingHorizonManager` and `Dispatcher`.

**The Worker Loop:**
```python
# This runs in the background constantly (e.g. every 30 seconds)
def dispatch_cron_job():
    # 1. Tell the queue to funnel ripe RAW orders into BATCHING and build Jobs
    jobs = rolling_horizon_manager.run_cycle()

    # 2. For every generated Job, query the database for Active Drivers
    for job in jobs:
        # DB Query: SELECT * FROM drivers WHERE status = 'AVAILABLE' OR status = 'TRANSIT_TO_COLLECT'
        db_drivers = DatabaseDriver.objects.filter(status__in=['available', 'transittoCollect'])
        
        # Convert DB models to pure Python Dataclass representations for the math engines
        pure_drivers = [Driver(id=d.id, location=(d.lat, d.lon), status=d.status) for d in db_drivers]
        
        # 3. Fire the Wave Dispatcher
        # IMPORTANT: This must be spawned as an async task so it doesn't block the loop!
        spawn_async_task(dispatcher.dispatch_job_async_loop, job, pure_drivers)
```

---

## 3. The Push Notification Webhook (AWS SNS / Firebase)

When `dispatch.dispatcher.py` executes Wave 1, it calls `self.push_service.broadcast_offer(driver_ids, job)`. You must implement this `PushService` interface to physically reach the driver's phone.

**Implementation Example:**
```python
class FirebasePushService:
    def broadcast_offer(self, driver_ids: List[str], job: Job):
        
        payload = {
            "type": "NEW_JOB_OFFER",
            "job_id": job.id,
            "total_payout": "$8.50", # You would calculate this in your business logic
            "pickup_coords": job.stops[0].coord,
            "num_orders": len(job.order_ids)
        }
        
        # Loop through Drivers, grab their Firebase FCM Device Tokens from the DB
        for driver_id in driver_ids:
            device_token = DatabaseDriver.objects.get(id=driver_id).fcm_token
            firebase.send_message(device_token, payload)
```

---

## 4. The Driver Acceptance Endpoint

When a driver receives the Firebase notification, they hit "Accept" in their React Native app. This hits your backend. This is where the **Distributed Database Lock** is crucial.

### Endpoint: `POST /api/jobs/{job_id}/accept`

**The Incoming Payload:**
```json
{
  "driver_id": "DRV-001"
}
```

**The Database Integration (The Race Condition Lock):**
```python
def accept_job_endpoint(request, job_id):
    driver_id = request.json["driver_id"]
    
    # 1. The Dispatcher tests the lock
    success = dispatcher.resolve_driver_acceptance(job_id, driver_id)
    
    if not success:
        return {"error": "Too late. Another driver already claimed this job."}, 409
        
    # 2. If true, the lock was acquired! Update your Postgres Database
    db_job = DatabaseJob.objects.get(id=job_id)
    db_job.assigned_driver_id = driver_id
    db_job.status = "ASSIGNED"
    db_job.save()
    
    # 3. Use the abstract State Machine to mathematically deduct driver capacity
    pure_driver = Driver(id=driver_id, max_capacity=5, status="AVAILABLE")
    pure_job = Job(id=job_id, order_ids=db_job.order_ids) # Convert DB Job to Dataclass
    
    updated_driver_state = handle_driver_acceptance(pure_driver, pure_job)
    
    # 4. Save the new capacity and status back to the DB
    db_driver = DatabaseDriver.objects.get(id=driver_id)
    db_driver.max_capacity = updated_driver_state.max_capacity
    db_driver.status = updated_driver_state.status
    db_driver.save()
    
    return {"message": "Job Secured!"}, 200
```
