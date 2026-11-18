#!/bin/bash
set -e
echo "=== HEALTH & GIS CAPABILITIES ==="
curl -s http://127.0.0.1:5000/api/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['platform'], '| DB:', d['subsystems']['incident_store'], '| Routing:', d['subsystems']['gis_routing_engine'])"

echo "=== DEM ELEVATION & RUNOFF ==="
curl -s "http://127.0.0.1:5000/api/gis/elevation?lon=3.4723&lat=6.4480" | python3 -c "import sys,json; d=json.load(sys.stdin); print('Elev:', d['elevation_m'], 'm | Slope:', d['slope_pct'], '% | Runoff:', d['runoff_compass'], '| Source:', d['dem_source'])"

echo "=== EMERGENCY ROUTING & FLOOD AVOIDANCE ==="
curl -s "http://127.0.0.1:5000/api/gis/route?dest_lon=3.4723&dest_lat=6.4480&service=fire" | python3 -c "import sys,json; d=json.load(sys.stdin); print('Origin:', d['origin_station']['name'], '| Dist:', d['distance_km'], 'km | ETA:', d['emergency_eta_min'], 'min')"

echo "=== SPATIAL POPULATION EXPOSURE ==="
curl -s "http://127.0.0.1:5000/api/gis/exposure?lon=3.4150&lat=6.4280&radius_m=1000" | python3 -c "import sys,json; d=json.load(sys.stdin); print('District:', d['district'], '| 1km Pop:', d['exposed_population'])"

echo "=== INCIDENTS & EXPORTS ==="
curl -s "http://127.0.0.1:5000/api/incidents" | python3 -c "import sys,json; d=json.load(sys.stdin); print('Loaded:', len(d), 'incidents')"
curl -s -o /dev/null -w "GeoJSON Export HTTP: %{http_code}\n" "http://127.0.0.1:5000/api/incidents/export?format=geojson"
curl -s -o /dev/null -w "CSV Export HTTP: %{http_code}\n" "http://127.0.0.1:5000/api/incidents/export?format=csv"
