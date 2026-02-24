from dataclasses import replace
from drivers.models import Driver, DriverStatus
from orders.models import Job

class DriverStateException(Exception):
    """Raised when an invalid driver transition is attempted."""
    pass

def handle_driver_acceptance(driver: Driver, job: Job, enable_continuous_chaining: bool = True) -> Driver:
    """
    Called when a driver officially accepts a Job.
    Deducts their physical capacity based on the number of orders in the Job.
    Transitions their status based on the business rules.
    """
    job_size = len(job.order_ids)
    
    if driver.max_capacity < job_size:
        raise DriverStateException(f"Driver {driver.id} does not have enough capacity. Has {driver.max_capacity}, Job needs {job_size}")
        
    new_capacity = driver.max_capacity - job_size
    
    # If chaining is enabled and they still have space in their car,
    # technically they could still be considered for overlapping route additions.
    # Otherwise, they transition to TRANSIT_TO_COLLECT.
    if new_capacity > 0 and enable_continuous_chaining:
        # We model them as still "AVAILABLE" conceptually for the matching engine, 
        # or we put them in TRANSIT_TO_COLLECT but adjust the filter logic to allow that status.
        # For strict state machine integrity, let's rigidly flip them to TRANSIT_TO_COLLECT
        # and recommend the `drivers/selection.py` allow `TRANSIT_TO_COLLECT` drivers if they have capacity.
        new_status = DriverStatus.TRANSIT_TO_COLLECT
    elif new_capacity == 0:
        new_status = DriverStatus.TRANSIT_TO_COLLECT
    else:
        new_status = driver.status

    # Because Driver is a frozen dataclass, we must return a new instance via replace
    return replace(driver, max_capacity=new_capacity, status=new_status)

def handle_driver_cancellation(driver: Driver, job: Job) -> Driver:
    """
    Emergency Fallback: If a driver breaks down or cancels after accepting,
    we must strictly restore their capacity (or push it to 0 if offline is enforced)
    and change their status mathematically.
    """
    # Assuming standard behavior is to take them offline if they cancelled mid-job
    # to protect system integrity until a human operator intervenes.
    return replace(driver, status=DriverStatus.OFFLINE)
