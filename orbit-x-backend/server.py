"""
ORBIT-X: Real-Time Telemetry & Threat Injection Server
Author: Team Aporia
"""

import asyncio
import json
import math
import numpy as np
from datetime import datetime, timezone
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from engine import ConjunctionEngine, teme_to_geodetic

app = FastAPI(
    title="ORBIT-X Telemetry Engine",
    description="Real-time SGP4 orbital propagation, conjunction assessment, and kinetic evasion solver.",
    version="1.0.0"
)

# Allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = ConjunctionEngine()

class ConnectionManager:
    """Manages active WebSocket connections defensively."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        payload = json.dumps(message)
        stale = []
        for conn in self.active_connections:
            try:
                await conn.send_text(payload)
            except Exception:
                stale.append(conn)
        for dead in stale:
            self.disconnect(dead)

manager = ConnectionManager()
simulated_threat_active = False

@app.get("/health")
async def health_check():
    return {
        "status": "nominal",
        "engine": "SGP4_cKDTree",
        "tracked_assets": len(engine.assets),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.post("/api/simulate-threat")
async def trigger_threat_simulation():
    """
    Demo Trigger: Deterministically forces a high-risk conjunction 
    and returns the along-track prograde burn maneuver.
    """
    global simulated_threat_active
    simulated_threat_active = True
    burn = engine.compute_evasion_burn(miss_dist_km=1.12, target_separation_km=28.5)
    return {
        "status": "threat_injected",
        "scenario": "CRITICAL_CONJUNCTION",
        "primary_asset": "STARLINK-1007",
        "threat_object": "COSMOS-2251-DEBRIS",
        "time_to_closest_approach_sec": 412,
        "miss_distance_km": 1.12,
        "collision_probability": 0.0894,
        "evasion_maneuver": burn
    }

@app.post("/api/reset-threat")
async def reset_threat():
    global simulated_threat_active
    simulated_threat_active = False
    return {"status": "nominal_state_restored"}

@app.websocket("/ws/telemetry")
async def websocket_telemetry_stream(websocket: WebSocket):
    """Streams propagated coordinates and alerts at 2 Hz."""
    await manager.connect(websocket)
    try:
        while True:
            now = datetime.now(timezone.utc)
            telemetry_batch = []
            
            for asset in engine.assets:
                state = asset.propagate(now)
                if state is not None:
                    pos_eci, vel_eci = state
                    lat, lon, alt = teme_to_geodetic(pos_eci, now)
                    velocity_mag = float(np.linalg.norm(vel_eci))
                    
                    telemetry_batch.append({
                        "id": asset.name,
                        "lat": round(lat, 4),
                        "lon": round(lon, 4),
                        "alt_km": round(alt, 2),
                        "velocity_kms": round(velocity_mag, 3),
                        "eci_position": [round(float(c), 2) for c in pos_eci]
                    })
                    
            payload = {
                "timestamp": now.isoformat(),
                "assets": telemetry_batch,
                "threat_alert": simulated_threat_active
            }
            
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(0.5)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
        