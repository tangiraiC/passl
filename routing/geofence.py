#Purpose: Road-network geofencing logic.
#Builds “eligible by reachability” sets using OSRM travel time/distance.
#Typical responsibilities:
#Given pickup point + rider positions → compute travel durations/distances
#Apply thresholds like:
#pickup_duration <= X minutes
#optional: pickup_distance <= Y km
#Batch logic (e.g., use OSRM /table and chunk riders)
#Sorting candidates by fastest arrival
#Output: a list of “geo-qualified candidates” with travel metrics.

from dataclasses import dataclass #for simple data structures
from typing import List, Tuple, Dict, Optional #for type annotations
from routing.osrm_client import OSRMClient 
#from routing.__init__ import estimate_eta 
import math 

#internal coordinate type :(lat,lon)
LatLon = Tuple[float, float]

@dataclass(frozen=True) #immutable data structure for geofence candidates
class GeofenceCandidate:
    """
    Represents a geofence qualified candidate with travel metrics.
    output of geofencing logic for a single rider.
    this is what the scoring layer will consume as input.
    out output is candidate + distance/duration to pickup.

    """

    rider_id: str
    pickup_distance_m: float # in meters -  from where rider is to pickup point
    pickup_duration_s: float # in seconds - from where rider is to pickup point
    dropoff_distance_m: float
    dropoff_duration_s: float 
    total_distance_m: float
    total_duration_s: float

def geofence_candidates(
        osrm: OSRMClient,
        pickup: LatLon,
        dropoff: LatLon,
        riders: List,
        *,
        max_pickup_duration_s: float = 900, #15 minutes default threshold
        max_pickup_distance_m: Optional[float] = None, #no distance threshold by default
        batch_size: int = 100 #for OSRM table batching,
) -> List[GeofenceCandidate]:
    
    """
    Road-network geofencing logic to find eligible riders based on OSRM travel time/distance.

    Purpose:
    - given a pickup location point + rider positions , compute travel durations/ distances using OSRM
    - filter riders by reachability thresholds (e.g., pickup_duration <= 15 minutes, optional: pickup_distance <= Y km)
    - return a list of geofence qualified candidates with travel metrics for scoring.

    Args:
        osrm: OSRMClient instance (HTTP adapter)
        pickup: (lat, lon) pickup coordinate
        riders: list of rider objects that have .id, .lat, .lon
        max_pickup_duration_s: duration threshold in seconds (e.g., 600 for 10 min)
        max_pickup_distance_m: optional distance threshold in meters (e.g., 5000 for 5 km)
        batch_size: chunk size for OSRM /table calls (keeps requests small)

    Returns:
        List[GeoCandidate], sorted by pickup_duration_s ascending. 
    """
    #defensive : empty rider list edge case
    if not riders:
        return []

    #Precompute dropoff -> rider distances/durations for later use in candidate construction
    delivery = osrm.compute_route([pickup, dropoff]) #tot be transefered to othe file
    dropoff_distance_m = delivery["distance"]   # or "distance" depending on your OSRMClient
    dropoff_duration_s = delivery["duration"]   # or "duration"

    candidates :  List[GeofenceCandidate] = []

    #Process riders in batches to avoid overly long URLs / huge OSRM calls
    for start in range(0, len(riders),batch_size):
        batch = riders[start:  start+batch_size] #get a batch of riders

        #build destinations in the same order as the batch
        destinations = [(rider.lat, rider.lon) for rider in batch] #list of (lat, lon) for OSRM table

        #one osrm call to get pickup -> each rider distance/duration
        matrix = osrm.compute_table(sources=[pickup], destinations=destinations) #returns dict with 'distances' and 'durations' lists

        durations = matrix["durations"] #list of durations from pickup to each rider
        distances = matrix["distances"] #list of distances from pickup to each rider

        #apply geofence thresholds and build candidates
        for index , rider in enumerate(batch):
            duration  = durations[index] if index < len(durations) else None 
            distance = distances[index] if index < len(distances) else None 

            #fail closed : if osrm cannot route (duration/distance is None), we treat as ineligible
            if duration is None or distance is None:
                continue
            #duration threshold -  if rider is too far in time, skip
            if duration > max_pickup_duration_s:
                continue
            # Distance threshold - if rider is too far in distance, skip
            if max_pickup_distance_m is not None and distance is not None:
                if distance > max_pickup_distance_m:
                    continue

            # this block  calculates total distance/duration for the entire route (pickup + dropoff) which can be used for more advanced scoring features later on (e.g., total ETA, total distance driven)
            total_distance_m = distance + dropoff_distance_m
            total_duration_s = duration + dropoff_duration_s

            #if we passed thresholds, add to candidates
            candidates.append(
                GeofenceCandidate(
                    
                    rider_id=rider.id,
                    pickup_distance_m=distance,
                    pickup_duration_s=duration,
                    dropoff_distance_m=dropoff_distance_m,
                    dropoff_duration_s=dropoff_duration_s,
                    total_distance_m=total_distance_m,
                    total_duration_s=total_duration_s,
                )
            )
        # sort by the fastest/shortest first (OSRM already gives us duration/distance, so we can sort candidates by pickup_duration_s)
        candidates.sort(
            key=lambda candidate:
              (candidate.pickup_duration_s, 
               candidate.pickup_distance_m, #primary sort by duration, secondary by distance
              )
        )
        return candidates

          


