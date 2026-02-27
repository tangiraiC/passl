"""
Purpose: Orchestrator / decision pipeline (the "glue").
What it does:
Accepts a created Job from the Orders module, separates the drivers into 5 geographic waves,
and simulates an asynchronous broadcast/timeout loop to assign the job gracefully.
"""

from typing import List
import time

from drivers.models import Driver
from drivers.selection import build_driver_waves
from drivers.policy import DriverPolicy, default_driver_policy
from orders.models import Job

class Dispatcher:
    """
    Coordinates the transaction of a Job to a Driver using 5 Cascading Waves.
    """
    def __init__(self, push_service=None, db_lock_manager=None, time_matrix_provider=None):
        self.push_service = push_service
        self.db_lock_manager = db_lock_manager
        self.time_matrix_provider = time_matrix_provider
        
    def dispatch_job_async_loop(self, job: Job, available_drivers: List[Driver], driver_policy: DriverPolicy = None):
        """
        Theoretical background task (e.g. executed by Celery or Redis Task Queue).
        It broadcasts to concentric waves one by one, waiting for a driver to accept.
        """
        driver_policy = driver_policy or default_driver_policy()
        
        waves = build_driver_waves(
            pickup_location=job.stops[0].coord,
            drivers=available_drivers,
            required_capacity=len(job.order_ids),
            policy=driver_policy,
            time_matrix_provider=self.time_matrix_provider
        )
        
        for wave_index, wave_drivers in enumerate(waves):
            if not wave_drivers:
                continue
                
            # Log the start of the wave
            wave_driver_ids = [driver.id for driver in wave_drivers]
            print(f"Broadcasting Job {job.id} to Wave {wave_index + 1} ({len(wave_drivers)} drivers)...")
            
            # 1. Update active state so drivers see the offer in their app
            if self.db_lock_manager:
                self.db_lock_manager.set_active_offer(job.id, wave_driver_ids, expires_in_sec=driver_policy.wave_timeout_seconds)
                
            # 2. Fire Push Notifications
            if self.push_service:
                self.push_service.broadcast_offer(wave_driver_ids, job)
                
            # 3. Wait for timeout or acceptance.
            # NOTE: In strictly asynchronous systems, this process would yield mathematically
            # instead of blocking time.sleep(). A delayed job would wake up `wave_timeout_seconds` later to 
            # execute Wave N+1. This sleep loop represents that theoretical design.
            time.sleep(driver_policy.wave_timeout_seconds)
            
            # Check if someone accepted during the timeout window
            if self.db_lock_manager and self.db_lock_manager.is_job_accepted(job.id):
                print(f"Job {job.id} was accepted by a driver in Wave {wave_index + 1}!")
                return
                
            # 4. If no one accepted, revoke the offer silently from this wave's devices
            #    so their UI drops the card, and proceed to the next wave.
            if self.push_service:
                self.push_service.revoke_offer(wave_driver_ids, job.id)
                
        print(f"All 5 waves exhausted. Job {job.id} failed to dispatch.")

    def resolve_driver_acceptance(self, job_id: str, driver_id: str) -> bool:
        """
        Race Condition Resolver: Called strictly when a mobile device hits "Accept" on the API.
        Guarantees that two drivers cannot accept the same Job simultaneously.
        """
        if not self.db_lock_manager:
            return False
            
        # 1. Acquire distributed lock to prevent 2 matching simultaneous requests
        with self.db_lock_manager.lock(f"job_{job_id}"):
            if self.db_lock_manager.is_job_accepted(job_id):
                return False # Too late, someone else already grabbed it!
                
            # 2. Mark as safely and exclusively accepted
            self.db_lock_manager.mark_job_accepted(job_id, driver_id)
            
            # 3. Send Silent Push notifications to everyone else in the active wave 
            #    who might still have the offer rendering on their screen.
            active_wave_driver_ids = self.db_lock_manager.get_active_offer_drivers(job_id)
            other_drivers = [other_driver_id for other_driver_id in active_wave_driver_ids if other_driver_id != driver_id]
            
            if self.push_service:
                self.push_service.revoke_offer(other_drivers, job_id)
                
            return True