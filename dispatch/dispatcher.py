"""
Purpose: Orchestrator / decision pipeline (the "glue").
What it does:
Accepts a created Job from the Orders module, grabs all system Drivers from the state,
calls the Driver selection algorithms, and then theoretically triggers a push notification
to the winner.

It does NOT make route decisions itself.
"""

from typing import List, Optional

from drivers.models import Driver
from drivers.selection import find_best_driver
from orders.models import Job

class Dispatcher:
    """
    Coordinates the transaction of a Job to a Driver.
    """
    def __init__(self, push_service=None):
        # Suppose we inject a service to actually hit FCM/APNS 
        self.push_service = push_service
        
    def dispatch_job(self, job: Job, available_drivers: List[Driver]) -> Optional[Driver]:
        """
        Takes a fully built job from the batching engine, and marries it to the best driver.
        """
        
        # 1. Ask the driver module to apply business rules and math to pick the winner.
        #    The pickup_location is simply the first Stop's coordinate in the Job sequence.
        best_driver = find_best_driver(
            pickup_location=job.stops[0].coord,
            drivers=available_drivers,
            required_capacity=len(job.order_ids) # A BATCH_3 job requires 3 capacity slots.
        )
        
        # 2. If no driver exists, we fail gracefully and log.
        if not best_driver:
            print(f"Failed to dispatch Job with {len(job.order_ids)} orders. No eligible drivers.")
            return None
            
        # 3. Otherwise, trigger external notification systems here (Twilio, Firebase, etc).
        print(f"Dispatching Job (Capacity {len(job.order_ids)}) to Driver {best_driver.id}!")
        if self.push_service:
            self.push_service.send_offer(best_driver.id, job)
            
        return best_driver