#Marks routing as a package.
#Optionally re-exports clean public APIs (e.g., OSRMClient, road_geofence, 
#estimate_eta) so other modules import from routing without knowing internal file names.
#No business logic.

#from .route_service import compute_route
#from .eta_service import estimate_eta   
from .osrm_client import OSRMClient
from .geofence import geofence_candidates
from .matrix_adapter import time_matrix_provider_from_osrm_client

__all__ = [
           "estimate_eta", 
           "OSRMClient",
             "road_geofence",
             "compute_route",
             "routeResult",
             "time_matrix_provider_from_osrm_client",
             ]
