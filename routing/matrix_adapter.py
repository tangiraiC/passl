from __future__ import annotations

from typing import List, Tuple

LatLon = Tuple[float, float]


class PreloadingTimeMatrixProvider:
    """
    Adapts your routing.osrm_client.OSRMClient into a batching-friendly
    time-matrix provider that supports caching and bulk prefetching.
    """
    def __init__(self, osrm_client):
        self.osrm_client = osrm_client
        self._cache = {}  # type: Dict[Tuple[float, float, float, float], float]

    def prefetch(self, coordinates: List[LatLon]) -> None:
        """
        Takes a list of unique coordinates and fetches the entire NxN table from OSRM once.
        Caches it in local memory so subsequent `__call__` lookups are instant.
        """
        num_coordinates = len(coordinates)
        if num_coordinates == 0:
            return

        table = self.osrm_client.compute_table(coordinates, coordinates)
        durations = table.get("durations", [])

        for src_idx, src in enumerate(coordinates):
            if src_idx >= len(durations): break
            for dest_idx, dest in enumerate(coordinates):
                if dest_idx >= len(durations[src_idx]): break
                duration = durations[src_idx][dest_idx]
                if duration is not None:
                    self._cache[(src[0], src[1], dest[0], dest[1])] = float(duration)

    def __call__(self, coordinates: List[LatLon]) -> List[List[float]]:
        num_coordinates = len(coordinates)
        if num_coordinates == 0:
            return []

        matrix = [[float('inf') for _ in range(num_coordinates)] for _ in range(num_coordinates)]

        # Check which coordinates we already have in cache
        has_missing = False
        for src_idx, src in enumerate(coordinates):
            for dest_idx, dest in enumerate(coordinates):
                key = (src[0], src[1], dest[0], dest[1])
                if key in self._cache:
                    matrix[src_idx][dest_idx] = self._cache[key]
                else:
                    has_missing = True

        # Fallback: If the engine asks for a coordinate we didn't prefetch, 
        # instantly fetch just what we need to satisfy safety constraints.
        if has_missing:
            table = self.osrm_client.compute_table(coordinates, coordinates)
            durations = table.get("durations", [])
            for src_idx, src in enumerate(coordinates):
                if src_idx >= len(durations): break
                for dest_idx, dest in enumerate(coordinates):
                    if dest_idx >= len(durations[src_idx]): break
                    duration = durations[src_idx][dest_idx]
                    if duration is not None:
                        val = float(duration)
                        self._cache[(src[0], src[1], dest[0], dest[1])] = val
                        matrix[src_idx][dest_idx] = val

        return matrix

def time_matrix_provider_from_osrm_client(osrm_client) -> PreloadingTimeMatrixProvider:
    """
    Legacy wrapper to maintain compatibility while returning the new preloader.
    """
    return PreloadingTimeMatrixProvider(osrm_client)