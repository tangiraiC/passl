#Purpose: The OSRM “adapter/client”.
#Sole responsibility: talk to OSRM via HTTP and return normalized outputs.
#Encapsulates OSRM-specific details:
#coordinate formatting (lon,lat)
#URL construction (/route, /table, etc.)
#timeouts/retries/error handling (if you implement)
#parsing response JSON into your internal shape
#It should not contain dispatch rules or scoring.


from dotenv import load_dotenv
import os
from typing import List, Tuple, Dict, Any, Optional
import requests

# Read OSRM base URL from environment
# Example in .env:
# BASE_URL=http://router.project-osrm.org
load_dotenv()
BASE_URL = os.getenv("BASE_URL")

# Internal coordinate type: (lat, lon)
LatLon = Tuple[float, float]

class OSMRError(Exception):
    """Custom exception for OSRM client errors."""
    pass

class OSRMClient:
    """
    OSRM Adapter / Client

    Sole responsibility:
    - Talk to OSRM via HTTP
    - Convert internal (lat, lon) → OSRM (lon,lat)
    - Return normalized outputs

    """
    def __init__(self,profile: str = "driving",timeout: int = 5):
        self.base_url = BASE_URL
        self.timeout = timeout #the tim to wait for a response from OSRM before giving up
        self.profile = profile #the mode of transportation (driving, walking, cycling)

        if not self.base_url:
            raise ValueError("OSRM base URL not set. Please set it in the .env file.")
        
        #----------------
        # Internal helper methods for coordinate formatting, URL construction, error handling, etc.
        #----------------
    def format_coordinates(self, coords: List[LatLon]) -> str:
            
        """Convert list of (lat, lon) to OSRM format 'lon,lat;lon,lat;...'"""
        return ';'.join([f"{lon},{lat}" for lat, lon in coords])
        #----------------
        # Public methods for route, table, etc.
        #----------------
    def compute_route(self, coordinates: List[LatLon]
                          ) -> Dict[str,float]:
            
        """
            calls the OSRM /routeendpoint with the given coordinates and 
            returns a dict with distance and duration
            
            Returns:
                {
                    "distance": float, # in meters
                    "duration": float, # in seconds
                }   
        """
        if len(coordinates) < 2:
                raise ValueError("At least two coordinates are required to compute a route.")
            
        coordinates = self.format_coordinates(coordinates)
        url = f"{self.base_url}/route/v1/{self.profile}/{coordinates}"

        response  = requests.get(
            url,
            params = {
                "overview": "false", # we don't need the geometry of the route
                  },
                timeout= self.timeout
        )

        data = response.json() #OSRM returns a JSON response with routes, each containing distance and duration

        #validating OSRM response
        if data.get("code") != "Ok":
            raise OSMRError(f"OSRM error: {data.get('message', 'Unknown error')}")
            
        route = data["routes"][0] #take the first route (OSRM may return multiple routes)

            #Normalize output to internal format
        return {
                "distance": route["distance"],
                "duration": route["duration"],
            }
        
        #----------------
        # table service (batch routing)
        #----------------
    def compute_table(self, sources: List[LatLon], 
                          destinations: List[LatLon]
                          ) -> Dict[Tuple[int, int],
                                    Dict[str, float]]:  #returns a dict mapping (source_index, dest_index) to distance and duration
            
            """
            calls ORSM /table endpoint .
            used for geofencing candidates (e.g., find all riders within 5km of the offer)

            returns :
            {
                (source_index, dest_index): {
                    "distance": float, # in meters
                    "duration": float, # in seconds
                },
                
            """
            if not destinations:
                return {'durations': [], 'distances': []} #defensive: if no destinations, return empty results

            # OSRM limits points. If sources == destinations (NxN matrix), 
            # we should not duplicate them in the URL.
            is_symmetric = (sources == destinations)
            
            if is_symmetric:
                coordinates = self.format_coordinates(sources)
                # OSRM by default computes all-to-all if sources/destinations aren't specified,
                # but we can specify them just in case.
                params = {
                    "annotations": "duration,distance",
                }
            else:
                coordinates = self.format_coordinates(sources + destinations)
                destination_index = ";".join(
                    str(i) for i in range(len(sources), len(sources) + len(destinations))
                )
                source_index = ";".join(str(i) for i in range(len(sources)))
                params = {
                    "sources": source_index,
                    "destinations": destination_index,
                    "annotations": "duration,distance",
                }

            url =  f"{self.base_url}/table/v1/{self.profile}/{coordinates}"

            response = requests.get(
                url,
                params=params,
                timeout=self.timeout
            )

            data = response.json() #OSRM returns a JSON response with table data

            if data.get("code") != "Ok":
                raise OSMRError(f"OSRM error: {data.get('message', 'Unknown error')}")
            
            # For symmetric NxN, distances/durations are just the full matrix.
            # Otherwise we'd have to slice them, but OSRM returns them as requested.
            distances = data["distances"] 
            durations = data["durations"] 
            
            # The original code assumed a 1xN query by doing `distances[0]`. 
            # But batching requires the full matrix! We return the full matrix.
            return {
                "durations": durations,
                "distances": distances, 
            }






            


