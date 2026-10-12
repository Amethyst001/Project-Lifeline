#!/bin/bash
echo "=== HEALTH ==="
curl -s http://127.0.0.1:5000/api/health

echo ""
echo "=== WEATHER ==="
curl -s "http://127.0.0.1:5000/api/weather/live" | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK:', d['weather_desc'], d['temperature_c'], 'C | Risk:', d['flood_risk_score'])"

echo ""
echo "=== INCIDENTS ==="
curl -s "http://127.0.0.1:5000/api/incidents" | python3 -c "import sys,json; d=json.load(sys.stdin); print('Loaded:', len(d), 'incidents')"

echo ""
echo "=== KPIs ==="
curl -s "http://127.0.0.1:5000/api/kpis" | python3 -c "import sys,json; d=json.load(sys.stdin); print('Active:', d['active_incidents'], '| Critical:', d['critical_sectors'])"

echo ""
echo "=== GEOJSON ==="
curl -s "http://127.0.0.1:5000/api/zones/geojson?service=flood" | python3 -c "import sys,json; d=json.load(sys.stdin); print('Flood features:', len(d['features']))"

echo ""
echo "=== N-ATLAS ENGLISH ==="
curl -s "http://127.0.0.1:5000/api/natlas/broadcast/lekki?lang=english&hazard=flood" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['broadcast_text'][:100])"

echo ""
echo "=== N-ATLAS YORUBA ==="
curl -s "http://127.0.0.1:5000/api/natlas/broadcast/lekki?lang=yoruba&hazard=flood" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['broadcast_text'][:100])"

echo ""
echo "=== N-ATLAS FIRE (PIDGIN) ==="
curl -s "http://127.0.0.1:5000/api/natlas/broadcast/lekki?lang=pidgin&hazard=fire" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['broadcast_text'][:100])"
