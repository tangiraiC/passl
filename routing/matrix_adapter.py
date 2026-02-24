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

    def prefetch(self, coords: List[LatLon]) -> None:
        """
        Takes a list of unique coordinates and fetches the entire NxN table from OSRM once.
        Caches it in local memory so subsequent `__call__` lookups are instant.
        """
        n = len(coords)
        if n == 0:
            return

        table = self.osrm_client.compute_table(coords, coords)
        durations = table.get("durations", [])

        for i, src in enumerate(coords):
            if i >= len(durations): break
            for j, dest in enumerate(coords):
                if j >= len(durations[i]): break
                duration = durations[i][j]
                if duration is not None:
                    self._cache[(src[0], src[1], dest[0], dest[1])] = float(duration)

    def __call__(self, coords: List[LatLon]) -> List[List[float]]:
        n = len(coords)
        if n == 0:
            return []

        m = [[float('inf') for _ in range(n)] for _ in range(n)]

        # Check which coords we already have in cache
        has_missing = False
        for i, src in enumerate(coords):
            for j, dest in enumerate(coords):
                key = (src[0], src[1], dest[0], dest[1])
                if key in self._cache:
                    m[i][j] = self._cache[key]
                else:
                    has_missing = True

        # Fallback: If the engine asks for a coordinate we didn't prefetch, 
        # instantly fetch just what we need to satisfy safety constraints.
        if has_missing:
            table = self.osrm_client.compute_table(coords, coords)
            durations = table.get("durations", [])
            for i, src in enumerate(coords):
                if i >= len(durations): break
                for j, dest in enumerate(coords):
                    if j >= len(durations[i]): break
                    duration = durations[i][j]
                    if duration is not None:
                        val = float(duration)
                        self._cache[(src[0], src[1], dest[0], dest[1])] = val
                        m[i][j] = val

        return m

def time_matrix_provider_from_osrm_client(osrm_client) -> PreloadingTimeMatrixProvider:
    """
    Legacy wrapper to maintain compatibility while returning the new preloader.
    """
    return PreloadingTimeMatrixProvider(osrm_client)