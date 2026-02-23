"""
Batching subpackage for the Orders domain.

Public API:
- batch_orders
- BatchResult
- BatchingPolicy
"""

from .engine import batch_orders, BatchResult
from .policy import BatchingPolicy, default_policy, peak_policy, offpeak_policy

__all__ = [
    "batch_orders",
    "BatchResult",
    "BatchingPolicy",
    "default_policy",
    "peak_policy",
    "offpeak_policy",
]