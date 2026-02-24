from typing import List
from orders.models import Order, OrderStatus, Job

class OrderStateException(Exception):
    """Raised when an invalid state transition is attempted."""
    pass

def transition_order_to_batching(order: Order) -> Order:
    """
    Called when the Rolling Horizon Queue picks up a RAW order 
    to feed it into the combinatorics engine.
    """
    if order.status not in [OrderStatus.RAW, OrderStatus.BATCHING]:
        raise OrderStateException(f"Cannot transition order {order.id} to BATCHING from {order.status}")
    
    order.status = OrderStatus.BATCHING
    return order

def transition_job_to_ready(job: Job) -> Job:
    """
    Called when the batching engine finishes creating a Job. 
    It locks all underlying Orders so they cannot be grabbed by another batch.
    """
    # Assuming we have the orders in memory, or we just update the DB records.
    # In a pure function, we would pass in the List[Order] to mutate them.
    # Since Job only holds order_ids, the actual Order entities must be updated in the repository layer.
    return job

def transition_orders_to_assigned(orders: List[Order]) -> List[Order]:
    """
    Once a driver accepts a Job, all its underlying Orders must be locked to ASSIGNED.
    """
    for order in orders:
        if order.status != OrderStatus.READY:
            raise OrderStateException(f"Order {order.id} is not READY. Current: {order.status}")
        order.status = OrderStatus.ASSIGNED
    return orders

def break_down_job_to_raw(orders: List[Order]) -> List[Order]:
    """
    Emergency Fallback: If a driver cancels, or a timeout completely fails,
    we shatter the Job and force the orders back to the start of the queue.
    """
    for order in orders:
        order.status = OrderStatus.RAW
    return orders
