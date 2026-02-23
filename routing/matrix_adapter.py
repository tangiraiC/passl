from __future__ import annotations

from typing import List, Tuple

LatLon = Tuple[float, float]


def time_matrix_provider_from_osrm_client(osrm_client):
    """
    Adapts your routing.osrm_client.OSRMClient into a batching-friendly
    time-matrix provider.

    Expected OSRMClient API (based on your earlier signature):
      compute_table(sources: List[LatLon], destinations: List[LatLon])
        -> Dict[(i, j)] -> {"duration": seconds, "distance": meters}
    """

    def provider(coords: List[LatLon]) -> List[List[float]]:
        #n is
        number_of_coordinates = len(coords)
        if number_of_coordinates == 0:
            return []

        table = osrm_client.compute_table(coords, coords)

        # Build NxN durations matrix
        #m is a 2D list of floats, where m[i][j] is the duration from coords[i] to coords[j]
        m = [[0.0 for _ in range(number_of_coordinates)] for _ in range(number_of_coordinates)] # m is initialized to 0, but will be overwritten by actual durations from OSRM
        for i in range(number_of_coordinates):
            for j in range(number_of_coordinates):
                cell = table.get((i, j))
                if cell is None:
                    # Fail safe: treat missing as very large
                    m[i][j] = float("inf")
                else:
                    # Use whichever key you store; common is "duration"
                    m[i][j] = float(cell.get("duration", float("inf")))
        return m

    return provider