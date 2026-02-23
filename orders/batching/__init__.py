"""
Batching subpackage for the Orders domain.

Public API:
- batch_orders
- BatchResult
- BatchingPolicy
"""

from .engine import batch_orders, BatchResult
from .policy import BatchingPolicy, default_policy, peak_policy, offpeak_policy
#from routing.matrix_adapter import time_matrix_provider_from_osrm_client
#from routing.osrm_client import OSRMClient
__all__ = [
    "batch_orders",
    "BatchResult",
    "BatchingPolicy",
    "default_policy",
    "peak_policy",
    "offpeak_policy",
]