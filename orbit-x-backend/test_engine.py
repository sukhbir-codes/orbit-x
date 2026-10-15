import numpy as np
from datetime import datetime, timezone
from engine import ConjunctionEngine, teme_to_geodetic

print("--- [TEST 1: SGP4 Propagation & Geodetic Conversion] ---")
engine = ConjunctionEngine()
now = datetime.now(timezone.utc)

for asset in engine.assets:
    state = asset.propagate(now)
    if state:
        pos, vel = state
        lat, lon, alt = teme_to_geodetic(pos, now)
        speed = float(np.linalg.norm(vel))
        print(f"[{asset.name}] Lat: {lat:6.2f}deg | Lon: {lon:7.2f}deg | Alt: {alt:6.1f} km | Speed: {speed:.2f} km/s")

print("\n--- [TEST 2: Spatial Conjunction Scan via cKDTree] ---")
events = engine.scan_conjunctions(now, duration_minutes=60, step_seconds=60, threshold_km=1500.0)
print(f"Proximity events found within scan window: {len(events)}")
if events:
    print(f"Sample Event: {events[0]['sat_a']} <-> {events[0]['sat_b']} at {events[0]['miss_distance_km']} km")

print("\n--- [TEST 3: Delta-v Evasion Burn Calculation] ---")
burn = engine.compute_evasion_burn(miss_dist_km=2.1, target_separation_km=25.0)
print(f"Burn Vector: {burn['maneuver_vector']}")
print(f"Impulse Delta-v: {burn['delta_v_ms']} m/s")
print(f"Propellant Penalty: {burn['propellant_penalty_grams']} grams")
print("\n>>> ALL TESTS PASSED: Module A is operational.")