"""
ORBIT-X: Core Orbital Kinematics & Conjunction Assessment Engine
Author: Team Aporia
"""

import math
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Tuple, Optional
from sgp4.api import Satrec, jday
from scipy.spatial import cKDTree

# WGS-84 Earth Constants
EARTH_RADIUS_KM = 6378.137

# Built-in TLE Snapshot for zero-crash fallback
DEFAULT_TLE_CATALOG = [
    {
        "name": "STARLINK-1007",
        "line1": "1 44713U 19074A   24288.50000000  .00001234  00000-0  12345-3 0  9991",
        "line2": "2 44713  53.0534 112.4321 0001452  89.2312 270.8912 15.06412345268912"
    },
    {
        "name": "COSMOS-2251-DEBRIS",
        "line1": "1 34123U 93036AAA 24288.50000000  .00005432  00000-0  54321-3 0  9998",
        "line2": "2 34123  74.0123 112.4410 0021450  45.1234 315.1234 14.89123452123456"
    },
    {
        "name": "ISS (ZARYA)",
        "line1": "1 25544U 98067A   24288.50000000  .00016717  00000-0  10270-3 0  9001",
        "line2": "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.49815771477435"
    }
]

class OrbitalAsset:
    def __init__(self, name: str, line1: str, line2: str):
        self.name = name
        self.line1 = line1
        self.line2 = line2
        self.satrec = Satrec.twoline2rv(line1, line2)
        
    def propagate(self, epoch_dt: datetime) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        jd, fr = jday(
            epoch_dt.year, epoch_dt.month, epoch_dt.day,
            epoch_dt.hour, epoch_dt.minute, epoch_dt.second + epoch_dt.microsecond * 1e-6
        )
        error_code, r, v = self.satrec.sgp4(jd, fr)
        if error_code != 0:
            return None
        return np.array(r), np.array(v)

def teme_to_geodetic(r_teme: np.ndarray, epoch_dt: datetime) -> Tuple[float, float, float]:
    x, y, z = r_teme
    
    jd, fr = jday(epoch_dt.year, epoch_dt.month, epoch_dt.day, epoch_dt.hour, epoch_dt.minute, epoch_dt.second)
    d = (jd - 2451545.0) + fr
    gmst_deg = (280.46061837 + 360.98564736629 * d) % 360.0
    gmst_rad = math.radians(gmst_deg)
    
    x_ecef = x * math.cos(gmst_rad) + y * math.sin(gmst_rad)
    y_ecef = -x * math.sin(gmst_rad) + y * math.cos(gmst_rad)
    z_ecef = z
    
    lon = math.degrees(math.atan2(y_ecef, x_ecef))
    r_xy = math.hypot(x_ecef, y_ecef)
    lat = math.degrees(math.atan2(z_ecef, r_xy))
    alt = math.sqrt(x**2 + y**2 + z**2) - EARTH_RADIUS_KM
    
    return lat, lon, alt

class ConjunctionEngine:
    def __init__(self, catalog: List[Dict[str, str]] = DEFAULT_TLE_CATALOG):
        self.assets = [OrbitalAsset(item["name"], item["line1"], item["line2"]) for item in catalog]

    def scan_conjunctions(
        self, 
        start_epoch: datetime, 
        duration_minutes: int = 120, 
        step_seconds: int = 60,
        threshold_km: float = 50.0
    ) -> List[Dict]:
        conjunctions = []
        num_steps = int((duration_minutes * 60) / step_seconds)
        
        for step in range(num_steps):
            current_dt = start_epoch + timedelta(seconds=step * step_seconds)
            positions = []
            valid_indices = []
            
            for idx, asset in enumerate(self.assets):
                res = asset.propagate(current_dt)
                if res is not None:
                    positions.append(res[0])
                    valid_indices.append(idx)
                    
            if len(positions) < 2:
                continue
                
            positions_arr = np.array(positions)
            tree = cKDTree(positions_arr)
            pairs = tree.query_pairs(r=threshold_km)
            
            for i, j in pairs:
                idx_a = valid_indices[i]
                idx_b = valid_indices[j]
                
                pos_a, vel_a = self.assets[idx_a].propagate(current_dt)
                pos_b, vel_b = self.assets[idx_b].propagate(current_dt)
                
                miss_distance = float(np.linalg.norm(pos_a - pos_b))
                rel_vel = float(np.linalg.norm(vel_a - vel_b))
                
                conjunctions.append({
                    "timestamp": current_dt.isoformat(),
                    "sat_a": self.assets[idx_a].name,
                    "sat_b": self.assets[idx_b].name,
                    "miss_distance_km": round(miss_distance, 3),
                    "relative_velocity_kms": round(rel_vel, 3)
                })
                
        return conjunctions

    def compute_evasion_burn(self, miss_dist_km: float, target_separation_km: float = 25.0) -> Dict:
        isp = 220.0
        g0 = 9.80665
        dry_mass_kg = 260.0
        
        delta_v_ms = abs(target_separation_km - miss_dist_km) * 0.125
        mass_fuel_kg = dry_mass_kg * (math.exp(delta_v_ms / (isp * g0)) - 1.0)
        
        return {
            "maneuver_vector": "ALONG_TRACK_PROGRADE",
            "delta_v_ms": round(delta_v_ms, 3),
            "propellant_penalty_grams": round(mass_fuel_kg * 1000, 2),
            "projected_separation_km": target_separation_km
        }