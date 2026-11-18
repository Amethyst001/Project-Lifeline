"""
Project Lifeline - Geospatial Intelligence, DEM Hydrology & Emergency Routing Engine
Provides production-grade spatial capabilities:
1. Digital Elevation Model (DEM) 3x3 Topographic Kernel & Flood Runoff Simulation
   - Live Copernicus GLO-90 DEM via Open-Meteo Elevation API (+ optional Mapbox Terrain)
   - Finite-difference slope gradient, aspect/runoff flow bearing, and sink basin detection
2. Turn-by-Turn Road Network Routing & Dynamic Flood Corridor Avoidance
   - Live Mapbox Directions (driving-traffic, Student Pack / Enterprise) when MAPBOX_ACCESS_TOKEN is set
   - Live OSRM OpenStreetMap Driving Engine fallback with zero configuration required
   - Geometric segment-to-hazard collision checks with automatic orthogonal bypass waypoint rerouting
3. Spatial Buffer Exposure & Demographic / Critical Asset Proximity Joins
   - CARTO Data/SQL API v3 integration when CARTO_API_TOKEN is set
   - High-resolution Lagos LGA/Ward demographic density surface & infrastructure spatial join
4. Lagos-Bounded Forward & Reverse Geocoding with Persistent SQLite Spatial Cache
"""

import os
import json
import math
import time
import sqlite3
import logging
from pathlib import Path
from threading import Lock
from typing import Dict, List, Any, Optional, Tuple
import requests

from geojson_data import LAGOS_SERVICES_GEOJSON
from weather_service import get_live_weather

logger = logging.getLogger("GISEngine")

DB_PATH = Path(__file__).parent / "lifeline.db"
CACHE_LOCK = Lock()

# Lagos Metropolitan Bounding Box [min_lon, min_lat, max_lon, max_lat]
LAGOS_BBOX = (2.7000, 6.3500, 4.3500, 6.7200)

# Georeferenced Lagos District Demographic & Hydrology Reference Centroids
# Population density values derived from Lagos Bureau of Statistics / WorldPop gridded estimates (hab/km2)
LAGOS_DISTRICTS = [
    {"name": "Lagos Island / Marina", "lon": 3.3910, "lat": 6.4530, "pop_density_km2": 34200, "drainage_capacity": 0.58},
    {"name": "Victoria Island", "lon": 3.4210, "lat": 6.4290, "pop_density_km2": 9400, "drainage_capacity": 0.52},
    {"name": "Ikoyi / Banana Island", "lon": 3.4380, "lat": 6.4540, "pop_density_km2": 6800, "drainage_capacity": 0.68},
    {"name": "Lekki Phase 1 / Oniru", "lon": 3.4723, "lat": 6.4450, "pop_density_km2": 8600, "drainage_capacity": 0.44},
    {"name": "Chevron / VGC Corridor", "lon": 3.5280, "lat": 6.4520, "pop_density_km2": 9800, "drainage_capacity": 0.46},
    {"name": "Ajah / Abraham Adesanya", "lon": 3.5680, "lat": 6.4670, "pop_density_km2": 13400, "drainage_capacity": 0.41},
    {"name": "Yaba / Lagos Mainland", "lon": 3.3780, "lat": 6.5090, "pop_density_km2": 24800, "drainage_capacity": 0.62},
    {"name": "Surulere", "lon": 3.3560, "lat": 6.4980, "pop_density_km2": 26900, "drainage_capacity": 0.60},
    {"name": "Apapa / Tin Can Port", "lon": 3.3640, "lat": 6.4450, "pop_density_km2": 12800, "drainage_capacity": 0.50},
    {"name": "Ilupeju / Mushin", "lon": 3.3610, "lat": 6.5440, "pop_density_km2": 31500, "drainage_capacity": 0.55},
    {"name": "Gbagada / Kosofe / Oworo", "lon": 3.3910, "lat": 6.5520, "pop_density_km2": 21200, "drainage_capacity": 0.54},
    {"name": "Ikeja / Alausa", "lon": 3.3550, "lat": 6.6050, "pop_density_km2": 15900, "drainage_capacity": 0.76},
    {"name": "Oshodi / Isolo", "lon": 3.3380, "lat": 6.5360, "pop_density_km2": 27400, "drainage_capacity": 0.57},
    {"name": "Festac / Amuwo-Odofin", "lon": 3.2840, "lat": 6.4690, "pop_density_km2": 18600, "drainage_capacity": 0.53},
    {"name": "Ikorodu", "lon": 3.5100, "lat": 6.6190, "pop_density_km2": 14200, "drainage_capacity": 0.64}
]

# Known Lagos Landmark Gazetteer for deterministic instant geocoding & offline resilience
LAGOS_LANDMARKS = {
    "admiralty way": (3.4723, 6.4480, "Admiralty Way, Lekki Phase 1"),
    "lekki phase 1": (3.4723, 6.4480, "Lekki Phase 1, Eti-Osa"),
    "lekki toll gate": (3.4520, 6.4365, "Lekki Toll Plaza, Eti-Osa"),
    "chevron": (3.5240, 6.4435, "Chevron Drive, Lekki"),
    "vgc": (3.5410, 6.4605, "Victoria Garden City (VGC), Lekki"),
    "ajah": (3.5680, 6.4670, "Ajah Roundabout / Abraham Adesanya"),
    "abraham adesanya": (3.5810, 6.4695, "Abraham Adesanya, Ajah"),
    "ahmadu bello": (3.4150, 6.4280, "Ahmadu Bello Way, Victoria Island"),
    "victoria island": (3.4215, 6.4295, "Victoria Island Central"),
    "ozumba mbadiwe": (3.4310, 6.4360, "Ozumba Mbadiwe Ave, Victoria Island"),
    "eko hotel": (3.4300, 6.4265, "Adetokunbo Ademola, Victoria Island"),
    "ikoyi": (3.4320, 6.4530, "Bourdillon / Awolowo Rd, Ikoyi"),
    "bourdillon": (3.4345, 6.4495, "Bourdillon Road, Ikoyi"),
    "banana island": (3.4525, 6.4640, "Banana Island, Ikoyi"),
    "third mainland": (3.3985, 6.4790, "Third Mainland Bridge Corridor"),
    "oworonshoki": (3.4015, 6.5465, "Oworonshoki Interchange"),
    "adeniji adele": (3.3945, 6.4610, "Adeniji Adele, Lagos Island"),
    "marina": (3.3880, 6.4520, "Marina, Lagos Island"),
    "broad street": (3.3910, 6.4530, "Broad Street, Lagos Island"),
    "eko bridge": (3.3760, 6.4670, "Eko Bridge / Apongbon"),
    "alausa": (3.3590, 6.6180, "Alausa Secretariat, Ikeja"),
    "ikeja": (3.3510, 6.5960, "Ikeja Central / Obafemi Awolowo Way"),
    "lasuth": (3.3510, 6.5920, "LASUTH, Ikeja"),
    "ilupeju": (3.3650, 6.5510, "Ilupeju Industrial Estate"),
    "gbagada": (3.3860, 6.5560, "Gbagada Expressway"),
    "yaba": (3.3760, 6.5140, "Herbert Macaulay Way, Yaba"),
    "surulere": (3.3560, 6.4980, "Bode Thomas / Adeniran Ogunsanya, Surulere"),
    "oshodi": (3.3420, 6.5540, "Oshodi Transport Interchange"),
    "apapa": (3.3640, 6.4450, "Creek Road, Apapa"),
    "ikorodu": (3.5100, 6.6190, "Ikorodu Central")
}


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in meters between two WGS84 coordinates."""
    r = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


def bearing_deg(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Initial compass bearing (0-360 deg) from point 1 to point 2."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlon)
    brng = math.degrees(math.atan2(x, y))
    return (brng + 360.0) % 360.0


def compass_label(deg: float) -> str:
    """Convert 0-360 bearing into 8-wind cardinal/intercardinal direction."""
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int(round(deg / 45.0)) % 8
    return dirs[idx]


def destination_point(lon: float, lat: float, bearing: float, dist_m: float) -> List[float]:
    """Project a coordinate along a compass bearing by dist_m meters."""
    r = 6371000.0
    ang_dist = dist_m / r
    brng = math.radians(bearing)
    phi1 = math.radians(lat)
    lam1 = math.radians(lon)

    phi2 = math.asin(
        math.sin(phi1) * math.cos(ang_dist) +
        math.cos(phi1) * math.sin(ang_dist) * math.cos(brng)
    )
    lam2 = lam1 + math.atan2(
        math.sin(brng) * math.sin(ang_dist) * math.cos(phi1),
        math.cos(ang_dist) - math.sin(phi1) * math.sin(phi2)
    )
    return [round(math.degrees(lam2), 6), round(math.degrees(phi2), 6)]


def point_to_segment_dist_m(
    px: float, py: float,
    ax: float, ay: float,
    bx: float, by: float
) -> float:
    """Minimum metric distance from point P(px, py) to line segment AB(ax,ay)-(bx,by)."""
    # Local equirectangular projection around Lagos latitude (~6.45N)
    cos_lat = math.cos(math.radians(6.45))
    m_per_deg_lon = 111320.0 * cos_lat
    m_per_deg_lat = 110574.0

    apx = (px - ax) * m_per_deg_lon
    apy = (py - ay) * m_per_deg_lat
    abx = (bx - ax) * m_per_deg_lon
    aby = (by - ay) * m_per_deg_lat

    ab_len_sq = abx * abx + aby * aby
    if ab_len_sq <= 1e-9:
        return math.hypot(apx, apy)

    t = max(0.0, min(1.0, (apx * abx + apy * aby) / ab_len_sq))
    proj_x = t * abx
    proj_y = t * aby
    return math.hypot(apx - proj_x, apy - proj_y)


class GISEngine:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_cache_table()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.execute("PRAGMA busy_timeout=10000;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_cache_table(self):
        with CACHE_LOCK:
            for attempt in range(5):
                try:
                    with self._get_conn() as conn:
                        conn.execute("PRAGMA journal_mode=WAL;")
                        conn.execute("""
                            CREATE TABLE IF NOT EXISTS spatial_cache (
                                cache_key TEXT PRIMARY KEY,
                                category TEXT NOT NULL,
                                payload_json TEXT NOT NULL,
                                created_at REAL NOT NULL
                            )
                        """)
                        conn.commit()
                    break
                except Exception as e:
                    if attempt == 4:
                        logger.warning(f"Spatial cache init warning: {e}")
                    time.sleep(0.15 * (attempt + 1))

    def _cache_get(self, key: str, max_age_sec: float = 86400.0) -> Optional[Any]:
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT payload_json, created_at FROM spatial_cache WHERE cache_key = ?",
                    (key,)
                ).fetchone()
                if row and (time.time() - row[1]) <= max_age_sec:
                    return json.loads(row[0])
        except Exception:
            pass
        return None

    def _cache_set(self, key: str, category: str, payload: Any):
        with CACHE_LOCK:
            try:
                with self._get_conn() as conn:
                    conn.execute(
                        """
                        INSERT INTO spatial_cache (cache_key, category, payload_json, created_at)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(cache_key) DO UPDATE SET
                            payload_json = excluded.payload_json,
                            created_at = excluded.created_at
                        """,
                        (key, category, json.dumps(payload), time.time())
                    )
                    conn.commit()
            except Exception as e:
                logger.debug(f"Cache write skipped: {e}")

    # ------------------------------------------------------------------
    # 1. PROVIDER CAPABILITIES (CARTO / MAPBOX / COPERNICUS / OSRM)
    # ------------------------------------------------------------------
    def get_capabilities(self) -> Dict[str, Any]:
        mapbox_token = os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()
        carto_token = os.getenv("CARTO_API_TOKEN", "").strip()
        carto_base = os.getenv("CARTO_API_BASE_URL", "https://gcp-us-east1.api.carto.com").strip()
        termii_key = os.getenv("TERMII_API_KEY", "").strip()
        gemini_key = os.getenv("GOOGLE_API_KEY", "").strip()

        public_mapbox = mapbox_token if mapbox_token.startswith("pk.") else None

        return {
            "basemap_providers": [
                "CARTO Dark Matter (Retina Vector Raster)",
                "CARTO Voyager Tactical",
                "Esri Dark Gray Canvas",
                "Esri World Imagery (Satellite)",
                "OpenTopoMap / Esri Terrain Contours"
            ],
            "dem_engine": {
                "provider": "Copernicus GLO-90 DEM (Open-Meteo Elevation API)",
                "resolution_m": 90,
                "status": "live"
            },
            "routing_engine": {
                "provider": "Mapbox Driving-Traffic API" if mapbox_token else "OSRM OpenStreetMap Road Network",
                "traffic_aware": bool(mapbox_token),
                "flood_avoidance": True,
                "status": "live"
            },
            "spatial_sql_engine": {
                "provider": "CARTO Spatial SQL v3 + Lagos WorldPop Grid" if carto_token else "Lagos WorldPop Gridded Spatial Engine (CARTO Ready)",
                "carto_api_base": carto_base,
                "carto_authenticated": bool(carto_token),
                "status": "live"
            },
            "student_pack_integrations": {
                "carto_basemaps": "active",
                "carto_spatial_sql": "authenticated" if carto_token else "standby_add_CARTO_API_TOKEN",
                "mapbox_routing_3d": "authenticated" if mapbox_token else "standby_add_MAPBOX_ACCESS_TOKEN"
            },
            "telecom_gateway": "live" if termii_key else "sandbox_ready",
            "vision_ai": "live" if gemini_key else "standby",
            "mapbox_public_token": public_mapbox
        }

    # ------------------------------------------------------------------
    # 2. DIGITAL ELEVATION MODEL (DEM) & HYDROLOGICAL RUNOFF SIMULATION
    # ------------------------------------------------------------------
    def analyze_elevation_and_runoff(
        self,
        lon: float,
        lat: float,
        rainfall_mm: Optional[float] = None,
        tide_surge_m: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Samples a 3x3 Copernicus 90m DEM grid around (lon, lat) to compute:
        - Elevation above mean sea level (m ASL)
        - Finite-difference terrain slope (%) and downslope runoff bearing
        - Topographic sink/depression trap detection
        - Dynamic stormwater ponding depth forecast (cm)
        """
        grid_key = f"dem3x3:{round(lon, 4)}:{round(lat, 4)}"
        grid_elevs = self._cache_get(grid_key, max_age_sec=86400 * 14)

        delta = 0.0025  # ~278m spacing around center
        # 3x3 row-major order: NW, N, NE, W, C, E, SW, S, SE
        offsets = [
            (-delta,  delta), (0.0,  delta), ( delta,  delta),
            (-delta,    0.0), (0.0,    0.0), ( delta,    0.0),
            (-delta, -delta), (0.0, -delta), ( delta, -delta)
        ]
        pts_lon = [round(lon + dx, 6) for dx, _ in offsets]
        pts_lat = [round(lat + dy, 6) for _, dy in offsets]

        source_label = "Copernicus GLO-90 DEM (Live)"

        if not grid_elevs or len(grid_elevs) != 9:
            try:
                lat_csv = ",".join(str(v) for v in pts_lat)
                lon_csv = ",".join(str(v) for v in pts_lon)
                url = f"https://api.open-meteo.com/v1/elevation?latitude={lat_csv}&longitude={lon_csv}"
                resp = requests.get(url, timeout=4.0)
                if resp.status_code == 200:
                    elev_list = resp.json().get("elevation", [])
                    if len(elev_list) == 9:
                        grid_elevs = [float(e if e is not None else 3.0) for e in elev_list]
                        self._cache_set(grid_key, "dem", grid_elevs)
            except Exception as e:
                logger.warning(f"DEM live lookup fallback: {e}")

        if not grid_elevs or len(grid_elevs) != 9:
            # Geomorphological coastal gradient fallback for Lagos (rises from Atlantic coast northward)
            source_label = "Lagos Coastal Geomorphology Model (Offline Fallback)"
            grid_elevs = []
            for plon, plat in zip(pts_lon, pts_lat):
                coastal_rise = max(1.0, (plat - 6.420) * 145.0)
                peninsula_dip = -1.8 if plon > 3.44 and plat < 6.47 else 0.0
                grid_elevs.append(round(max(0.8, coastal_rise + peninsula_dip), 1))

        z_nw, z_n, z_ne, z_w, z_c, z_e, z_sw, z_s, z_se = grid_elevs
        neighbors = [z_nw, z_n, z_ne, z_w, z_e, z_sw, z_s, z_se]
        min_elev = min(grid_elevs)
        max_elev = max(grid_elevs)
        mean_neighbor = sum(neighbors) / 8.0

        # Metric grid cell spacing at Lagos latitude
        dx_m = delta * 111320.0 * math.cos(math.radians(lat))
        dy_m = delta * 110574.0

        # Horn's 3x3 finite-difference surface gradient (dz/dx East, dz/dy North)
        dz_dx = ((z_ne + 2.0 * z_e + z_se) - (z_nw + 2.0 * z_w + z_sw)) / (8.0 * dx_m)
        dz_dy = ((z_nw + 2.0 * z_n + z_ne) - (z_sw + 2.0 * z_s + z_se)) / (8.0 * dy_m)

        slope_rad = math.atan(math.hypot(dz_dx, dz_dy))
        slope_deg = round(math.degrees(slope_rad), 2)
        slope_pct = round(math.hypot(dz_dx, dz_dy) * 100.0, 2)

        # Downslope runoff vector points opposite to uphill gradient (-dz_dx, -dz_dy)
        if abs(dz_dx) < 1e-6 and abs(dz_dy) < 1e-6:
            # Flat coastal plain: water drains toward nearest lower neighbor or south toward lagoon/coast
            lowest_idx = min(range(9), key=lambda idx: grid_elevs[idx])
            if lowest_idx != 4 and grid_elevs[lowest_idx] < z_c:
                runoff_brng = bearing_deg(lon, lat, pts_lon[lowest_idx], pts_lat[lowest_idx])
            else:
                runoff_brng = 185.0  # Coastal/lagoon drainage southward
        else:
            # Compass bearing from East=-dz_dx, North=-dz_dy
            runoff_brng = (math.degrees(math.atan2(-dz_dx, -dz_dy)) + 360.0) % 360.0

        runoff_brng = round(runoff_brng, 1)
        runoff_dir = compass_label(runoff_brng)
        runoff_target = destination_point(lon, lat, runoff_brng, 550.0)

        # Topographic depression / retention basin check
        depression_m = round(mean_neighbor - z_c, 2)
        is_sink_basin = depression_m >= 0.25 or (z_c <= 3.5 and slope_pct < 0.35)

        # Dynamic hydrologic ponding simulation combining weather + DEM + drainage capacity
        if rainfall_mm is None or tide_surge_m is None:
            w = get_live_weather()
            if rainfall_mm is None:
                rainfall_mm = float(w.get("precipitation_mm", 0.0))
            if tide_surge_m is None:
                tide_surge_m = float(w.get("atlantic_tide_surge_m", 0.5))

        nearest_dist_info = min(
            LAGOS_DISTRICTS,
            key=lambda d: haversine_m(lon, lat, d["lon"], d["lat"])
        )
        drainage_eff = nearest_dist_info["drainage_capacity"]

        # Tidal backflow impact when ground elevation is below 5m ASL
        tidal_backwater_cm = max(0.0, (5.2 - z_c) * tide_surge_m * 6.5) if z_c < 5.2 else 0.0
        rain_runoff_cm = rainfall_mm * (1.85 - drainage_eff)
        sink_multiplier = 1.45 if is_sink_basin else (0.75 if slope_pct > 1.2 else 1.0)
        predicted_ponding_cm = int(round(max(0.0, (tidal_backwater_cm + rain_runoff_cm) * sink_multiplier)))

        if z_c <= 2.5 or predicted_ponding_cm >= 40:
            hydro_risk = "CRITICAL"
        elif z_c <= 5.0 or is_sink_basin or predicted_ponding_cm >= 18:
            hydro_risk = "HIGH"
        elif z_c <= 10.0 or predicted_ponding_cm >= 8:
            hydro_risk = "MODERATE"
        else:
            hydro_risk = "LOW"

        if predicted_ponding_cm >= 38:
            vehicle_clearance = "AMPHIBIOUS_OR_CANOE_ONLY"
        elif predicted_ponding_cm >= 18:
            vehicle_clearance = "HIGH_CLEARANCE_TRUCK_ONLY"
        else:
            vehicle_clearance = "ALL_EMERGENCY_VEHICLES"

        return {
            "coordinates": [round(lon, 6), round(lat, 6)],
            "elevation_m": round(z_c, 1),
            "surrounding_min_m": round(min_elev, 1),
            "surrounding_max_m": round(max_elev, 1),
            "mean_neighbor_m": round(mean_neighbor, 2),
            "slope_pct": slope_pct,
            "slope_deg": slope_deg,
            "runoff_bearing_deg": runoff_brng,
            "runoff_compass": runoff_dir,
            "runoff_vector_line": [
                [round(lon, 6), round(lat, 6)],
                runoff_target
            ],
            "is_sink_basin": is_sink_basin,
            "depression_depth_m": depression_m,
            "drainage_efficiency": drainage_eff,
            "predicted_ponding_cm": predicted_ponding_cm,
            "hydro_risk_level": hydro_risk,
            "vehicle_clearance": vehicle_clearance,
            "dem_source": source_label
        }

    # ------------------------------------------------------------------
    # 3. TURN-BY-TURN ROUTING & DYNAMIC FLOOD HAZARD AVOIDANCE
    # ------------------------------------------------------------------
    def get_active_flood_hazards(self, active_incidents: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """Compile all active submerged flood corridors (water >= 30cm) that block road vehicles."""
        hazards: List[Dict[str, Any]] = []
        seen_coords = set()

        # 1. Live reported flood incidents
        if active_incidents:
            for inc in active_incidents:
                if inc.get("status") == "RESOLVED":
                    continue
                water_cm = int(inc.get("water_depth_cm") or 0)
                if inc.get("service") == "flood" and water_cm >= 30:
                    coords = inc.get("coordinates") or [inc.get("lon", 0), inc.get("lat", 0)]
                    if len(coords) >= 2 and coords[0] and coords[1]:
                        key = (round(coords[0], 3), round(coords[1], 3))
                        if key not in seen_coords:
                            seen_coords.add(key)
                            hazards.append({
                                "id": inc.get("id", "flood_inc"),
                                "name": inc.get("location", "Submerged Corridor"),
                                "lon": float(coords[0]),
                                "lat": float(coords[1]),
                                "water_cm": water_cm,
                                "radius_m": 420.0 if water_cm >= 45 else 280.0
                            })

        # 2. Monitored GeoJSON flood basins >= 30cm
        for feat in LAGOS_SERVICES_GEOJSON.get("features", []):
            props = feat.get("properties", {})
            if props.get("category") == "flood" and int(props.get("water_cm", 0)) >= 30:
                lon, lat = feat["geometry"]["coordinates"]
                key = (round(lon, 3), round(lat, 3))
                if key not in seen_coords:
                    seen_coords.add(key)
                    w_cm = int(props["water_cm"])
                    hazards.append({
                        "id": feat.get("id", "flood_zone"),
                        "name": props.get("name", "Flood Zone"),
                        "lon": float(lon),
                        "lat": float(lat),
                        "water_cm": w_cm,
                        "radius_m": 420.0 if w_cm >= 45 else 280.0
                    })

        return hazards

    def _check_route_flood_collisions(
        self,
        coords_lonlat: List[List[float]],
        flood_hazards: List[Dict[str, Any]],
        dest_lon: float,
        dest_lat: float
    ) -> List[Dict[str, Any]]:
        """
        Check if a GeoJSON LineString intersects any flood hazard zone,
        excluding the final 250m approach when the destination itself is inside that flood zone.
        """
        hits = []
        if not coords_lonlat or len(coords_lonlat) < 2:
            return hits

        for hz in flood_hazards:
            hlon, hlat, hrad = hz["lon"], hz["lat"], hz["radius_m"]
            # If destination itself is inside this flood zone, amphibious approach is expected at terminus
            if haversine_m(dest_lon, dest_lat, hlon, hlat) <= hrad * 0.85:
                continue

            min_dist = float("inf")
            for i in range(len(coords_lonlat) - 1):
                ax, ay = coords_lonlat[i][0], coords_lonlat[i][1]
                bx, by = coords_lonlat[i + 1][0], coords_lonlat[i + 1][1]
                d = point_to_segment_dist_m(hlon, hlat, ax, ay, bx, by)
                if d < min_dist:
                    min_dist = d
                if min_dist <= hrad:
                    break

            if min_dist <= hrad:
                hits.append({
                    "id": hz["id"],
                    "name": hz["name"],
                    "water_cm": hz["water_cm"],
                    "clearance_m": round(min_dist, 1),
                    "coordinates": [hlon, hlat]
                })
        return hits

    def _find_candidate_stations(self, dest_lon: float, dest_lat: float, service: str) -> List[Dict[str, Any]]:
        """Select candidate responder stations for the requested emergency category."""
        svc = (service or "flood").lower()
        target_cat = svc
        # Flood dispatch uses fire/rescue + flood staging assets
        allowed_cats = [target_cat] if svc != "flood" else ["fire", "flood"]

        stations = []
        for feat in LAGOS_SERVICES_GEOJSON.get("features", []):
            props = feat.get("properties", {})
            cat = props.get("category")
            # For flood incidents, avoid picking the exact same flooded point at 0m as its own station
            lon, lat = feat["geometry"]["coordinates"]
            dist_m = haversine_m(lon, lat, dest_lon, dest_lat)
            if svc == "flood" and cat == "flood" and dist_m < 150.0:
                continue
            if cat in allowed_cats:
                stations.append({
                    "id": feat.get("id"),
                    "name": props.get("name"),
                    "category": cat,
                    "dispatch_asset": props.get("dispatch_asset", "Rapid Response Unit"),
                    "contact": props.get("contact", "767 / 112"),
                    "coordinates": [lon, lat],
                    "air_distance_km": round(dist_m / 1000.0, 2)
                })

        if not stations:
            # Fallback to any station
            for feat in LAGOS_SERVICES_GEOJSON.get("features", []):
                props = feat.get("properties", {})
                lon, lat = feat["geometry"]["coordinates"]
                stations.append({
                    "id": feat.get("id"),
                    "name": props.get("name"),
                    "category": props.get("category", "emergency"),
                    "dispatch_asset": props.get("dispatch_asset", "Emergency Unit"),
                    "contact": props.get("contact", "112"),
                    "coordinates": [lon, lat],
                    "air_distance_km": round(haversine_m(lon, lat, dest_lon, dest_lat) / 1000.0, 2)
                })

        stations.sort(key=lambda s: s["air_distance_km"])
        return stations[:3]

    def _fetch_road_routes(
        self,
        waypoints_lonlat: List[List[float]],
        exclude_points: Optional[List[Tuple[float, float]]] = None
    ) -> Tuple[List[Dict[str, Any]], str]:
        """Query Mapbox Driving-Traffic (if configured) or live OSRM road network."""
        coord_str = ";".join(f"{pt[0]:.6f},{pt[1]:.6f}" for pt in waypoints_lonlat)
        cache_key = f"route:{coord_str}:{len(exclude_points or [])}"
        cached = self._cache_get(cache_key, max_age_sec=900.0)
        if cached:
            return cached["routes"], cached["provider"]

        mapbox_token = os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()
        if mapbox_token:
            try:
                mb_url = (
                    f"https://api.mapbox.com/directions/v5/mapbox/driving-traffic/{coord_str}"
                    f"?alternatives=true&geometries=geojson&overview=full&steps=true&access_token={mapbox_token}"
                )
                if exclude_points:
                    excl = ",".join(f"point({lon:.5f} {lat:.5f})" for lon, lat in exclude_points[:5])
                    mb_url += f"&exclude={requests.utils.quote(excl)}"
                r = requests.get(mb_url, timeout=4.5)
                if r.status_code == 200:
                    data = r.json()
                    if data.get("routes"):
                        parsed = self._normalize_osrm_mapbox_routes(data["routes"])
                        self._cache_set(cache_key, "route", {"routes": parsed, "provider": "Mapbox Driving-Traffic API"})
                        return parsed, "Mapbox Driving-Traffic API"
            except Exception as e:
                logger.warning(f"Mapbox routing fallback to OSRM: {e}")

        # Live OSRM Road Routing Engine
        try:
            osrm_url = (
                f"https://router.project-osrm.org/route/v1/driving/{coord_str}"
                f"?overview=full&geometries=geojson&steps=true&alternatives=true"
            )
            r = requests.get(osrm_url, headers={"User-Agent": "ProjectLifeline-GIS/2.0"}, timeout=4.5)
            if r.status_code == 200:
                data = r.json()
                if data.get("code") == "Ok" and data.get("routes"):
                    parsed = self._normalize_osrm_mapbox_routes(data["routes"])
                    self._cache_set(cache_key, "route", {"routes": parsed, "provider": "OSRM Road Network Engine"})
                    return parsed, "OSRM Road Network Engine"
        except Exception as e:
            logger.warning(f"OSRM live routing fallback: {e}")

        # Geometric corridor fallback if completely offline
        p1, p2 = waypoints_lonlat[0], waypoints_lonlat[-1]
        dist_m = haversine_m(p1[0], p1[1], p2[0], p2[1]) * 1.28
        dur_s = dist_m / 9.5  # ~34 km/h urban emergency speed
        mid = [(p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0]
        fallback_routes = [{
            "geometry": {"type": "LineString", "coordinates": [p1, mid, p2]},
            "distance_m": dist_m,
            "duration_s": dur_s,
            "steps": [
                {"instruction": "Depart responder station on primary arterial", "road_name": "Arterial Corridor", "distance_m": round(dist_m * 0.6), "duration_s": round(dur_s * 0.6)},
                {"instruction": "Arrive at emergency incident perimeter", "road_name": "Target Sector", "distance_m": round(dist_m * 0.4), "duration_s": round(dur_s * 0.4)}
            ]
        }]
        return fallback_routes, "Offline Arterial Corridor Estimator"

    def _normalize_osrm_mapbox_routes(self, raw_routes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = []
        for rt in raw_routes:
            steps_out = []
            for leg in rt.get("legs", []):
                for st in leg.get("steps", []):
                    maneuver = st.get("maneuver", {})
                    m_type = maneuver.get("type", "continue").replace("_", " ").capitalize()
                    modifier = maneuver.get("modifier", "")
                    road = st.get("name") or st.get("ref") or "Local Road"
                    instr = maneuver.get("instruction") or (
                        f"{m_type} {modifier} onto {road}".strip() if road else f"{m_type} {modifier}".strip()
                    )
                    if st.get("distance", 0) >= 25 or m_type.lower() in ["depart", "arrive"]:
                        steps_out.append({
                            "instruction": instr,
                            "road_name": road,
                            "distance_m": round(float(st.get("distance", 0))),
                            "duration_s": round(float(st.get("duration", 0)))
                        })
            normalized.append({
                "geometry": rt.get("geometry"),
                "distance_m": float(rt.get("distance", 0.0)),
                "duration_s": float(rt.get("duration", 0.0)),
                "steps": steps_out[:18]
            })
        return normalized

    def compute_emergency_route(
        self,
        dest_lon: float,
        dest_lat: float,
        service: str = "flood",
        origin_lon: Optional[float] = None,
        origin_lat: Optional[float] = None,
        avoid_floods: bool = True,
        active_incidents: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Compute optimal road-network emergency dispatch route with dynamic flood hazard avoidance.
        """
        flood_hazards = self.get_active_flood_hazards(active_incidents)

        if origin_lon is not None and origin_lat is not None:
            station = {
                "id": "custom_origin",
                "name": "Custom Dispatch Origin",
                "category": service,
                "dispatch_asset": "Assigned Emergency Unit",
                "contact": "767 / 112",
                "coordinates": [float(origin_lon), float(origin_lat)],
                "air_distance_km": round(haversine_m(origin_lon, origin_lat, dest_lon, dest_lat) / 1000.0, 2)
            }
        else:
            candidates = self._find_candidate_stations(dest_lon, dest_lat, service)
            station = candidates[0]

        orig = station["coordinates"]
        dest = [round(float(dest_lon), 6), round(float(dest_lat), 6)]
        excl = [(h["lon"], h["lat"]) for h in flood_hazards] if avoid_floods else None

        routes, provider = self._fetch_road_routes([orig, dest], exclude_points=excl)
        annotated = []
        for rt in routes:
            coords = rt["geometry"]["coordinates"]
            hits = self._check_route_flood_collisions(coords, flood_hazards, dest[0], dest[1])
            annotated.append({**rt, "flood_hits": hits})

        primary = annotated[0]
        selected = primary
        compromised_route = None
        flood_detour_applied = False

        if avoid_floods and primary["flood_hits"]:
            # 1. Check if an alternative route is completely clear of flood zones
            clean_alts = [r for r in annotated[1:] if len(r["flood_hits"]) == 0]
            if clean_alts:
                selected = clean_alts[0]
                compromised_route = primary
                flood_detour_applied = True
            else:
                # 2. Compute orthogonal bypass waypoint around the first flooded corridor
                hz = primary["flood_hits"][0]
                route_brng = bearing_deg(orig[0], orig[1], dest[0], dest[1])
                # Try both +90 deg and -90 deg perpendicular offsets (950m clearance)
                for offset_angle in [90.0, -90.0]:
                    wp = destination_point(hz["coordinates"][0], hz["coordinates"][1], (route_brng + offset_angle) % 360.0, 950.0)
                    detour_rts, _ = self._fetch_road_routes([orig, wp, dest])
                    if detour_rts:
                        det_coords = detour_rts[0]["geometry"]["coordinates"]
                        det_hits = self._check_route_flood_collisions(det_coords, flood_hazards, dest[0], dest[1])
                        if len(det_hits) < len(primary["flood_hits"]):
                            selected = {**detour_rts[0], "flood_hits": det_hits}
                            compromised_route = primary
                            flood_detour_applied = True
                            break

        dist_km = round(selected["distance_m"] / 1000.0, 2)
        civilian_min = round(selected["duration_s"] / 60.0, 1)
        # Siren & emergency lane priority factor (0.78x civilian travel time, minimum 1.2 min)
        emergency_eta_min = round(max(1.2, civilian_min * 0.78), 1)

        detour_delta_km = 0.0
        detour_delta_min = 0.0
        if compromised_route:
            detour_delta_km = round(max(0.0, (selected["distance_m"] - compromised_route["distance_m"]) / 1000.0), 2)
            detour_delta_min = round(max(0.0, (selected["duration_s"] - compromised_route["duration_s"]) / 60.0 * 0.78), 1)

        return {
            "provider": provider,
            "origin_station": station,
            "destination": dest,
            "distance_km": dist_km,
            "civilian_duration_min": civilian_min,
            "emergency_eta_min": emergency_eta_min,
            "geometry": selected["geometry"],
            "steps": selected["steps"],
            "intersects_flood": len(selected["flood_hits"]) > 0,
            "flood_zones_hit": selected["flood_hits"],
            "flood_detour_applied": flood_detour_applied,
            "detour_delta_km": detour_delta_km,
            "detour_delta_min": detour_delta_min,
            "compromised_direct_geometry": compromised_route["geometry"] if compromised_route else None,
            "compromised_flood_zones": compromised_route["flood_hits"] if compromised_route else [],
            "active_flood_hazards_count": len(flood_hazards)
        }

    # ------------------------------------------------------------------
    # 4. SPATIAL BUFFER EXPOSURE & CARTO DEMOGRAPHIC / ASSET ANALYTICS
    # ------------------------------------------------------------------
    def analyze_spatial_exposure(self, lon: float, lat: float, radius_m: float = 1000.0) -> Dict[str, Any]:
        """
        Calculate population exposure, vulnerable demographics, structures at risk,
        and spatial proximity join to emergency facilities within buffer radius.
        Uses CARTO SQL API v3 when CARTO_API_TOKEN is configured, paired with Lagos WorldPop grid.
        """
        radius_km = max(0.1, min(10.0, radius_m / 1000.0))
        area_km2 = math.pi * (radius_km ** 2)

        # Inverse-distance weighted interpolation across Lagos district density surface
        weights_sum = 0.0
        weighted_density = 0.0
        nearest_district = LAGOS_DISTRICTS[0]
        nearest_dist_m = float("inf")

        for dist in LAGOS_DISTRICTS:
            d_m = haversine_m(lon, lat, dist["lon"], dist["lat"])
            if d_m < nearest_dist_m:
                nearest_dist_m = d_m
                nearest_district = dist
            w = 1.0 / ((max(350.0, d_m) / 1000.0) ** 2)
            weights_sum += w
            weighted_density += w * dist["pop_density_km2"]

        est_density_km2 = int(round(weighted_density / max(1e-6, weights_sum)))
        # Water body / lagoon attenuation if point is far out in Lagos Lagoon
        if 3.395 <= lon <= 3.445 and 6.468 <= lat <= 6.535:
            est_density_km2 = int(est_density_km2 * 0.25)

        exposed_pop = int(round(est_density_km2 * area_km2))
        vulnerable_pop = int(round(exposed_pop * 0.215))  # Children <5 & elderly >65 (~21.5%)
        structures_est = int(round(exposed_pop / 14.5))

        # Optional CARTO Spatial SQL v3 live enrichment if CARTO_API_TOKEN is configured
        carto_token = os.getenv("CARTO_API_TOKEN", "").strip()
        carto_source = "Lagos WorldPop & LBS Spatial Grid"
        if carto_token:
            carto_base = os.getenv("CARTO_API_BASE_URL", "https://gcp-us-east1.api.carto.com").rstrip("/")
            carto_conn = os.getenv("CARTODB_CONNECTION", "carto_dw")
            carto_table = os.getenv("CARTO_POPULATION_TABLE", "").strip()
            if carto_table:
                try:
                    sql = (
                        f"SELECT SUM(population) AS pop FROM `{carto_table}` "
                        f"WHERE ST_DWithin(geom, ST_GeogPoint({lon:.6f}, {lat:.6f}), {radius_m:.1f})"
                    )
                    resp = requests.get(
                        f"{carto_base}/v3/sql/{carto_conn}/query",
                        params={"q": sql},
                        headers={"Authorization": f"Bearer {carto_token}"},
                        timeout=4.0
                    )
                    if resp.status_code == 200:
                        rows = resp.json().get("rows", [])
                        if rows and rows[0].get("pop") is not None:
                            exposed_pop = int(round(float(rows[0]["pop"])))
                            vulnerable_pop = int(round(exposed_pop * 0.215))
                            carto_source = "CARTO Spatial SQL v3 Live Warehouse"
                except Exception as ce:
                    logger.warning(f"CARTO SQL query fallback to local grid: {ce}")

        # Spatial Proximity Join against all georeferenced emergency & infrastructure assets
        nearby_assets = []
        for feat in LAGOS_SERVICES_GEOJSON.get("features", []):
            props = feat.get("properties", {})
            alon, alat = feat["geometry"]["coordinates"]
            d_m = haversine_m(lon, lat, alon, alat)
            brng = bearing_deg(lon, lat, alon, alat)
            nearby_assets.append({
                "id": feat.get("id"),
                "name": props.get("name"),
                "category": props.get("category"),
                "dispatch_asset": props.get("dispatch_asset"),
                "distance_km": round(d_m / 1000.0, 2),
                "bearing_compass": compass_label(brng),
                "coordinates": [alon, alat]
            })

        nearby_assets.sort(key=lambda x: x["distance_km"])

        nearest_by_type = {}
        for cat in ["fire", "medical", "crime", "infrastructure"]:
            match = next((a for a in nearby_assets if a["category"] == cat), None)
            if match:
                nearest_by_type[cat] = match

        return {
            "coordinates": [round(lon, 6), round(lat, 6)],
            "buffer_radius_m": round(radius_m),
            "buffer_area_km2": round(area_km2, 2),
            "district": nearest_district["name"],
            "population_density_km2": est_density_km2,
            "exposed_population": exposed_pop,
            "vulnerable_population": vulnerable_pop,
            "estimated_structures": structures_est,
            "nearest_responders": nearest_by_type,
            "assets_within_3km": [a for a in nearby_assets if a["distance_km"] <= 3.5][:6],
            "spatial_source": carto_source
        }

    def _batch_prefetch_dem_grids(self, centers_lonlat: List[Tuple[float, float]]):
        """Batch-fetch multiple 3x3 Copernicus DEM grids in a single HTTP request (up to 90 points)."""
        delta = 0.0025
        offsets = [
            (-delta,  delta), (0.0,  delta), ( delta,  delta),
            (-delta,    0.0), (0.0,    0.0), ( delta,    0.0),
            (-delta, -delta), (0.0, -delta), ( delta, -delta)
        ]
        uncached_keys = []
        batch_lons = []
        batch_lats = []

        for lon, lat in centers_lonlat[:10]:
            grid_key = f"dem3x3:{round(lon, 4)}:{round(lat, 4)}"
            if not self._cache_get(grid_key, max_age_sec=86400 * 14):
                uncached_keys.append(grid_key)
                for dx, dy in offsets:
                    batch_lons.append(str(round(lon + dx, 6)))
                    batch_lats.append(str(round(lat + dy, 6)))

        if not uncached_keys:
            return

        try:
            url = f"https://api.open-meteo.com/v1/elevation?latitude={','.join(batch_lats)}&longitude={','.join(batch_lons)}"
            resp = requests.get(url, timeout=5.0)
            if resp.status_code == 200:
                elevs = resp.json().get("elevation", [])
                if len(elevs) == len(uncached_keys) * 9:
                    for idx, g_key in enumerate(uncached_keys):
                        chunk = [float(e if e is not None else 3.0) for e in elevs[idx * 9:(idx + 1) * 9]]
                        self._cache_set(g_key, "dem", chunk)
        except Exception as e:
            logger.warning(f"Batch DEM prefetch fallback: {e}")

    def build_risk_surface_geojson(self, active_incidents: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Generate GeoJSON FeatureCollection of hydrological flood basins, runoff vectors,
        and active incident impact buffers for tactical GIS visualization.
        """
        features = []
        weather = get_live_weather()
        rain = float(weather.get("precipitation_mm", 0.0))
        surge = float(weather.get("atlantic_tide_surge_m", 0.5))

        hydro_feats = [
            feat for feat in LAGOS_SERVICES_GEOJSON.get("features", [])
            if feat.get("properties", {}).get("category") in ["flood", "infrastructure"]
        ]
        self._batch_prefetch_dem_grids([tuple(f["geometry"]["coordinates"]) for f in hydro_feats])

        # 1. Monitored hydrological nodes + live DEM runoff vector lines
        for feat in hydro_feats:
            props = feat.get("properties", {})
            lon, lat = feat["geometry"]["coordinates"]
            dem = self.analyze_elevation_and_runoff(lon, lat, rainfall_mm=rain, tide_surge_m=surge)
            features.append({
                "type": "Feature",
                "properties": {
                    "layer_type": "runoff_vector",
                    "name": props.get("name"),
                    "elevation_m": dem["elevation_m"],
                    "slope_pct": dem["slope_pct"],
                    "runoff_compass": dem["runoff_compass"],
                    "hydro_risk": dem["hydro_risk_level"],
                    "predicted_ponding_cm": max(int(props.get("water_cm", 0)), dem["predicted_ponding_cm"])
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": dem["runoff_vector_line"]
                }
            })

        # 2. Active incident spatial exposure centroids
        for inc in (active_incidents or []):
            if inc.get("status") == "RESOLVED":
                continue
            coords = inc.get("coordinates")
            if coords and len(coords) >= 2:
                lon, lat = float(coords[0]), float(coords[1])
                exp = self.analyze_spatial_exposure(lon, lat, radius_m=800.0)
                features.append({
                    "type": "Feature",
                    "properties": {
                        "layer_type": "exposure_zone",
                        "incident_id": inc.get("id"),
                        "service": inc.get("service"),
                        "severity": inc.get("severity"),
                        "radius_m": 800 if inc.get("severity") == "CRITICAL" else 500,
                        "exposed_population": exp["exposed_population"],
                        "district": exp["district"]
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [lon, lat]
                    }
                })

        return {
            "type": "FeatureCollection",
            "features": features
        }

    # ------------------------------------------------------------------
    # 5. LAGOS-BOUNDED GEOCODING & REVERSE GEOCODING
    # ------------------------------------------------------------------
    def geocode_lagos(self, query: str) -> Dict[str, Any]:
        """Resolve a Lagos address or landmark to exact [lon, lat] coordinates."""
        q_clean = (query or "").strip()
        if not q_clean:
            return {"coordinates": [3.4500, 6.4450], "display_name": "Lagos Island / Eti-Osa", "source": "default"}

        q_lower = q_clean.lower()
        for key, (lon, lat, label) in LAGOS_LANDMARKS.items():
            if key in q_lower:
                return {"coordinates": [lon, lat], "display_name": label, "source": "Lagos Gazetteer"}

        cache_key = f"geo:{q_lower}"
        cached = self._cache_get(cache_key, max_age_sec=86400 * 30)
        if cached:
            return cached

        # Mapbox Geocoding if configured
        mb_token = os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()
        if mb_token:
            try:
                bbox_str = f"{LAGOS_BBOX[0]},{LAGOS_BBOX[1]},{LAGOS_BBOX[2]},{LAGOS_BBOX[3]}"
                mb_url = (
                    f"https://api.mapbox.com/geocoding/v5/mapbox.places/{requests.utils.quote(q_clean + ', Lagos, Nigeria')}.json"
                    f"?bbox={bbox_str}&limit=1&access_token={mb_token}"
                )
                r = requests.get(mb_url, timeout=3.5)
                if r.status_code == 200 and r.json().get("features"):
                    feat = r.json()["features"][0]
                    res = {
                        "coordinates": [round(feat["center"][0], 6), round(feat["center"][1], 6)],
                        "display_name": feat.get("place_name", q_clean),
                        "source": "Mapbox Geocoding API"
                    }
                    self._cache_set(cache_key, "geocode", res)
                    return res
            except Exception as e:
                logger.warning(f"Mapbox geocode fallback: {e}")

        # OpenStreetMap Nominatim strictly bounded to Lagos State
        try:
            viewbox = f"{LAGOS_BBOX[0]},{LAGOS_BBOX[3]},{LAGOS_BBOX[2]},{LAGOS_BBOX[1]}"
            nom_url = (
                f"https://nominatim.openstreetmap.org/search"
                f"?q={requests.utils.quote(q_clean + ', Lagos, Nigeria')}"
                f"&format=json&limit=1&viewbox={viewbox}&bounded=1"
            )
            r = requests.get(nom_url, headers={"User-Agent": "ProjectLifeline-GIS/2.0"}, timeout=3.5)
            if r.status_code == 200 and len(r.json()) > 0:
                first = r.json()[0]
                res = {
                    "coordinates": [round(float(first["lon"]), 6), round(float(first["lat"]), 6)],
                    "display_name": first.get("display_name", q_clean).split(", Lagos")[0],
                    "source": "OpenStreetMap Nominatim"
                }
                self._cache_set(cache_key, "geocode", res)
                return res
        except Exception as e:
            logger.warning(f"Nominatim geocode fallback: {e}")

        return {"coordinates": [3.4500, 6.4450], "display_name": q_clean, "source": "Lagos Centroid Fallback"}

    def reverse_geocode_lagos(self, lon: float, lat: float) -> Dict[str, Any]:
        """Resolve [lon, lat] into a human-readable Lagos street / district name."""
        cache_key = f"revgeo:{round(lon, 4)}:{round(lat, 4)}"
        cached = self._cache_get(cache_key, max_age_sec=86400 * 30)
        if cached:
            return cached

        try:
            nom_url = f"https://nominatim.openstreetmap.org/reverse?lat={lat:.6f}&lon={lon:.6f}&format=json&zoom=17"
            r = requests.get(nom_url, headers={"User-Agent": "ProjectLifeline-GIS/2.0"}, timeout=3.5)
            if r.status_code == 200:
                data = r.json()
                addr = data.get("address", {})
                road = addr.get("road") or addr.get("neighbourhood") or addr.get("suburb") or addr.get("residential")
                area = addr.get("suburb") or addr.get("city_district") or addr.get("town") or addr.get("county") or "Lagos"
                label = f"{road}, {area}" if road and road != area else (road or area)
                res = {
                    "coordinates": [round(lon, 6), round(lat, 6)],
                    "location": label,
                    "full_address": data.get("display_name", label),
                    "source": "OpenStreetMap Nominatim"
                }
                self._cache_set(cache_key, "revgeo", res)
                return res
        except Exception as e:
            logger.warning(f"Reverse geocode fallback: {e}")

        nearest = min(LAGOS_DISTRICTS, key=lambda d: haversine_m(lon, lat, d["lon"], d["lat"]))
        return {
            "coordinates": [round(lon, 6), round(lat, 6)],
            "location": f"{nearest['name']} ({lat:.4f}°N, {lon:.4f}°E)",
            "full_address": nearest["name"],
            "source": "Lagos District Spatial Index"
        }


gis_engine = GISEngine()
