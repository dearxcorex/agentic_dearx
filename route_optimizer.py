"""Advanced route optimization algorithms for FM station inspection"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from scipy.spatial.distance import cdist
from haversine import haversine
import networkx as nx
from itertools import combinations
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RouteOptimizer:
    """Advanced route optimization using multiple algorithms"""

    def __init__(self, speed_kmh: float = 40):
        self.speed_kmh = speed_kmh
        self.inspection_time_minutes = 10

    def optimize_route(self,
                      stations: List[Dict],
                      start_location: Tuple[float, float],
                      max_time_minutes: Optional[float] = None,
                      algorithm: str = "adaptive") -> Dict:
        """
        Optimize route using specified algorithm

        Algorithms:
        - nearest_neighbor: Fast, simple greedy approach
        - 2opt: Local search optimization
        - christofides: Approximation algorithm for TSP
        - adaptive: Choose best algorithm based on problem size
        """

        if not stations:
            return {"order": [], "total_distance": 0, "total_time": 0}

        # Prepare distance matrix
        locations = [start_location] + [(s["latitude"], s["longitude"]) for s in stations]
        distance_matrix = self._create_distance_matrix(locations)

        # Choose algorithm
        n_stations = len(stations)
        if algorithm == "adaptive":
            if n_stations <= 10:
                algorithm = "brute_force" if n_stations <= 8 else "christofides"
            elif n_stations <= 25:
                algorithm = "2opt"
            else:
                algorithm = "nearest_neighbor"

        logger.info(f"Using {algorithm} algorithm for {n_stations} stations")

        # Run optimization
        if algorithm == "nearest_neighbor":
            order = self._nearest_neighbor(distance_matrix)
        elif algorithm == "2opt":
            order = self._two_opt(distance_matrix)
        elif algorithm == "christofides":
            order = self._christofides(distance_matrix)
        elif algorithm == "brute_force" and n_stations <= 8:
            order = self._brute_force(distance_matrix)
        else:
            order = self._nearest_neighbor(distance_matrix)

        # Apply time constraint if specified
        if max_time_minutes:
            order = self._apply_time_constraint(
                order, distance_matrix, max_time_minutes
            )

        # Calculate metrics
        metrics = self._calculate_route_metrics(order, distance_matrix)

        return {
            "order": [i - 1 for i in order if i > 0],  # Adjust for start location
            "metrics": metrics,
            "algorithm_used": algorithm
        }

    def _create_distance_matrix(self, locations: List[Tuple[float, float]]) -> np.ndarray:
        """Create distance matrix between all locations"""
        n = len(locations)
        matrix = np.zeros((n, n))

        for i in range(n):
            for j in range(i + 1, n):
                distance = haversine(locations[i], locations[j])
                matrix[i, j] = distance
                matrix[j, i] = distance

        return matrix

    def _nearest_neighbor(self, distance_matrix: np.ndarray) -> List[int]:
        """Nearest neighbor greedy algorithm"""
        n = len(distance_matrix)
        unvisited = set(range(1, n))  # Exclude start (index 0)
        current = 0
        route = []

        while unvisited:
            # Find nearest unvisited
            distances = [(distance_matrix[current, i], i) for i in unvisited]
            distances.sort()
            nearest = distances[0][1]

            route.append(nearest)
            unvisited.remove(nearest)
            current = nearest

        return route

    def _two_opt(self, distance_matrix: np.ndarray) -> List[int]:
        """2-opt local search optimization"""
        # Start with nearest neighbor solution
        route = self._nearest_neighbor(distance_matrix)

        improved = True
        while improved:
            improved = False
            for i in range(len(route) - 1):
                for j in range(i + 2, len(route)):
                    # Calculate distances for current and swapped routes
                    current_dist = self._segment_distance(route, i, j, distance_matrix)
                    new_route = route[:i] + route[i:j][::-1] + route[j:]
                    new_dist = self._segment_distance(new_route, i, j, distance_matrix)

                    if new_dist < current_dist:
                        route = new_route
                        improved = True
                        break
                if improved:
                    break

        return route

    def _segment_distance(self,
                         route: List[int],
                         start: int,
                         end: int,
                         distance_matrix: np.ndarray) -> float:
        """Calculate distance for a route segment"""
        distance = 0
        prev = 0 if start == 0 else route[start - 1]

        for i in range(start, min(end, len(route))):
            current = route[i]
            distance += distance_matrix[prev, current]
            prev = current

        return distance

    def _christofides(self, distance_matrix: np.ndarray) -> List[int]:
        """Christofides algorithm for TSP approximation"""
        n = len(distance_matrix)
        if n <= 2:
            return list(range(1, n))

        # Create complete graph
        G = nx.Graph()
        for i in range(n):
            for j in range(i + 1, n):
                G.add_edge(i, j, weight=distance_matrix[i, j])

        # Find minimum spanning tree
        mst = nx.minimum_spanning_tree(G)

        # Find odd degree vertices
        odd_vertices = [v for v in mst.nodes() if mst.degree(v) % 2 == 1]

        # Find minimum weight perfect matching on odd vertices
        if odd_vertices:
            odd_graph = G.subgraph(odd_vertices).copy()
            # Simple greedy matching (not perfect but fast)
            matching = self._greedy_matching(odd_graph, distance_matrix)

            # Add matching edges to MST
            for u, v in matching:
                mst.add_edge(u, v, weight=distance_matrix[u, v])

        # Find Eulerian circuit
        eulerian = list(nx.eulerian_circuit(mst, source=0))

        # Convert to Hamiltonian by skipping repeated vertices
        visited = set()
        route = []
        for u, v in eulerian:
            if u not in visited and u != 0:
                route.append(u)
                visited.add(u)
            if v not in visited and v != 0:
                route.append(v)
                visited.add(v)

        return route

    def _greedy_matching(self, graph: nx.Graph, distance_matrix: np.ndarray) -> List[Tuple[int, int]]:
        """Greedy matching for odd degree vertices"""
        vertices = list(graph.nodes())
        matching = []
        matched = set()

        # Sort edges by weight
        edges = []
        for u, v in combinations(vertices, 2):
            if u not in matched and v not in matched:
                edges.append((distance_matrix[u, v], u, v))

        edges.sort()

        # Greedily select edges
        for weight, u, v in edges:
            if u not in matched and v not in matched:
                matching.append((u, v))
                matched.add(u)
                matched.add(v)
                if len(matched) == len(vertices):
                    break

        return matching

    def _brute_force(self, distance_matrix: np.ndarray) -> List[int]:
        """Brute force for small problems (n <= 8)"""
        from itertools import permutations

        n = len(distance_matrix)
        stations = list(range(1, n))

        best_route = None
        best_distance = float('inf')

        for perm in permutations(stations):
            distance = distance_matrix[0, perm[0]]
            for i in range(len(perm) - 1):
                distance += distance_matrix[perm[i], perm[i + 1]]

            if distance < best_distance:
                best_distance = distance
                best_route = list(perm)

        return best_route

    def _apply_time_constraint(self,
                              route: List[int],
                              distance_matrix: np.ndarray,
                              max_time_minutes: float) -> List[int]:
        """Trim route to fit within time constraint"""
        trimmed_route = []
        total_time = 0
        prev = 0

        for station in route:
            # Calculate travel time
            travel_time = (distance_matrix[prev, station] / self.speed_kmh) * 60
            station_time = travel_time + self.inspection_time_minutes

            if total_time + station_time > max_time_minutes:
                break

            trimmed_route.append(station)
            total_time += station_time
            prev = station

        return trimmed_route

    def _calculate_route_metrics(self,
                                route: List[int],
                                distance_matrix: np.ndarray) -> Dict:
        """Calculate detailed route metrics"""
        if not route:
            return {
                "total_distance_km": 0,
                "total_time_minutes": 0,
                "total_travel_time_minutes": 0,
                "total_inspection_time_minutes": 0
            }

        total_distance = 0
        prev = 0

        for station in route:
            total_distance += distance_matrix[prev, station]
            prev = station

        total_travel_time = (total_distance / self.speed_kmh) * 60
        total_inspection_time = len(route) * self.inspection_time_minutes
        total_time = total_travel_time + total_inspection_time

        return {
            "total_distance_km": round(total_distance, 2),
            "total_time_minutes": round(total_time, 1),
            "total_travel_time_minutes": round(total_travel_time, 1),
            "total_inspection_time_minutes": total_inspection_time,
            "stations_visited": len(route)
        }