#Expose the high-level pipeline pieces:
#Candidate filtering (hard rules)
#Scoring / ranking
#Dispatcher orchestrator (the “one call” entry point)

# Expose the high-level pipeline pieces:
from .dispatcher import Dispatcher

__all__ = [
    "Dispatcher",
]