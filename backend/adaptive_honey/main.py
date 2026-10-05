from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import CommandRequest, CreateSessionRequest
from .service import HoneyService

BASE = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv("ADAPTIVE_HONEY_DB", BASE / "data" / "adaptive_honey.db"))
FRONTEND = BASE.parent / "frontend"

app = FastAPI(title="AdaptiveHoney", version="0.1.0", description="Behavior-aware cyber deception research prototype")
service = HoneyService(DB_PATH)
clients: set[WebSocket] = set()


async def broadcast(payload: dict):
    stale=[]
    for client in clients:
        try: await client.send_json(payload)
        except Exception: stale.append(client)
    for client in stale: clients.discard(client)


def detail(session_id: str):
    record=service.store.get_session(session_id)
    if not record: raise HTTPException(404,"session not found")
    events=service.store.events(session_id)
    return {**record,"events":events,"techniques":service.store.techniques(session_id),"indicators":service.store.indicators(session_id)}


@app.get("/api/health")
def health(): return {"status":"healthy","containment":"emulation-only","version":"0.1.0"}


@app.post("/api/sessions", status_code=201)
async def create_session(body: CreateSessionRequest):
    state,current_profile=service.create(body.persona_id,body.source_ip,body.username)
    await broadcast({"type":"session_created","session_id":state.id})
    return {"state":state,"profile":current_profile}


@app.get("/api/sessions")
def sessions():
    result=[]
    for row in service.store.all_sessions():
        state=row["state"]; sid=state["id"]
        result.append({"id":sid,"hostname":state["persona"]["hostname"],"persona":state["persona"]["label"],"username":state["username"],"source_ip":state["source_ip"],"status":state["status"],"created_at":state["created_at"],"command_count":len(state["history"]),"profile":row["profile"],"techniques":service.store.techniques(sid)})
    return result


@app.get("/api/sessions/{session_id}")
def session_detail(session_id: str): return detail(session_id)


@app.post("/api/sessions/{session_id}/commands")
async def run_command(session_id: str, body: CommandRequest):
    try: state,current_profile,event,techniques,indicators=service.command(session_id,body.command)
    except KeyError: raise HTTPException(404,"session not found")
    except ValueError as exc: raise HTTPException(409,str(exc))
    await broadcast({"type":"command","session_id":session_id,"event":event.model_dump()})
    return {"state":state,"profile":current_profile,"event":event,"new_techniques":techniques,"new_indicators":indicators}


@app.get("/api/sessions/{session_id}/replay")
def replay(session_id: str):
    data=detail(session_id)
    return {"schema":"adaptive-honey/replay-v1","exported_at":data["state"]["created_at"],**data}


@app.get("/api/metrics")
def metrics():
    counts=service.store.counts(); sessions=service.store.all_sessions(); latencies=[]; fallbacks=0
    for row in sessions:
        for event in service.store.events(row["state"]["id"]):
            latencies.append(event["latency_ms"])
            fallbacks += event["response"]["exit_code"]==127
    latencies.sort()
    p95=latencies[min(len(latencies)-1,int(len(latencies)*.95))] if latencies else 0
    return {**counts,"active_sessions":sum(r["state"]["status"]=="active" for r in sessions),"median_latency_ms":latencies[len(latencies)//2] if latencies else 0,"p95_latency_ms":p95,"fallbacks":fallbacks,"consistency_violations":0}


@app.websocket("/ws/sessions")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept(); clients.add(ws)
    try:
        while True: await ws.receive_text()
    except WebSocketDisconnect: clients.discard(ws)


if FRONTEND.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND), name="assets")

    @app.get("/", include_in_schema=False)
    def dashboard(): return FileResponse(FRONTEND / "index.html")
