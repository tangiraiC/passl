"""
Purpose: Package entry + stable exports.
What it does:

Marks orders as a Python package.

Optionally re-exports the public API so other modules can do:

from orders import Order, Job, batch_orders

Should not contain business logic.

Orders domain package.

Public API:
- Domain models: Order, Job, Stop, OrderStatus, JobType
- (Later) batching entry: batch_orders

"""
from .models import Order, Job, Stop, OrderStatus, JobType

__all__ = ["Order", 
           "Job",
             "Stop",
               "OrderStatus"
               , "JobType"
               ]