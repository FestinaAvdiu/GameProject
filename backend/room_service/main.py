# Create rooms

# Let users join rooms (verifying the user exists via User Service)

# Keep room state in memory

# When two players are present, notify the Game Rules Service (POST /start) so the game can begin

# backend/room_service/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
import uuid
import httpx

app = FastAPI(title="Room Service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory room storage
# room_id -> {"name": str, "players": [username,...], "status": "waiting"/"playing"}
rooms: Dict[str, Dict] = {}

# Config: where User Service and Game Service live
USER_SERVICE_URL = "http://localhost:8001"
GAME_SERVICE_URL = "http://localhost:8003"

# Request models
class CreateRoomReq(BaseModel):
    room_name: str
    creator: str  # username

class JoinRoomReq(BaseModel):
    room_id: str
    username: str

@app.post("/create_room")
def create_room(req: CreateRoomReq):
    # Check if room name already exists
    for room_id, room in rooms.items():
        if room["name"] == req.room_name:
            raise HTTPException(status_code=400, detail="Room name already exists. Choose a different name.")
    
    # verify user exists by calling User Service
    try:
        r = httpx.get(f"{USER_SERVICE_URL}/users/{req.creator}", timeout=3.0)
        if r.status_code != 200:
            raise HTTPException(status_code=400, detail="Creator user not found")
    except httpx.RequestError:
        raise HTTPException(status_code=500, detail="Could not reach User Service")

    room_id = str(uuid.uuid4())[:8]
    rooms[room_id] = {
        "name": req.room_name,
        "players": [req.creator],
        "status": "waiting"
    }
    return {"room_id": room_id, "room": rooms[room_id]}

@app.post("/join_room")
def join_room(req: JoinRoomReq):
    room = rooms.get(req.room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # verify user exists
    try:
        r = httpx.get(f"{USER_SERVICE_URL}/users/{req.username}", timeout=3.0)
        if r.status_code != 200:
            raise HTTPException(status_code=400, detail="User not found")
    except httpx.RequestError:
        raise HTTPException(status_code=500, detail="Could not reach User Service")

    if req.username in room["players"]:
        return {"message": "User already in room", "room": room}

    if len(room["players"]) >= 2:
        raise HTTPException(status_code=400, detail="Room is full")

    room["players"].append(req.username)

    # If two players in the room, tell Game Rules Service to start the game
    if len(room["players"]) == 2:
        payload = {"room_id": req.room_id, "players": room["players"]}
        try:
            # best-effort notification to Game Service
            resp = httpx.post(f"{GAME_SERVICE_URL}/start", json=payload, timeout=5.0)
            if resp.status_code != 200:
                print("Game Service returned non-200:", resp.status_code, resp.text)
        except Exception as e:
            print("Warning: Could not notify Game Service:", e)

        room["status"] = "playing"

    return {"room_id": req.room_id, "room": room}

@app.post("/reset_room/{room_id}")
def reset_room(room_id: str):
    """Reset room after game ends - keep room but clear players"""
    room = rooms.get(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    room["players"] = []
    room["status"] = "waiting"
    return {"message": "Room reset", "room_id": room_id, "room": room}

@app.delete("/room/{room_id}")
def delete_room(room_id: str):
    """Delete a room (called when game ends)"""
    if room_id in rooms:
        del rooms[room_id]
        return {"message": "Room deleted", "room_id": room_id}
    raise HTTPException(status_code=404, detail="Room not found")

@app.post("/leave_room")
def leave_room(req: JoinRoomReq):
    """Remove a player from a room"""
    room = rooms.get(req.room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    if req.username in room["players"]:
        room["players"].remove(req.username)
        
        # If room is empty, delete it
        if len(room["players"]) == 0:
            del rooms[req.room_id]
            return {"message": "Room deleted (empty)", "room_id": req.room_id}
        
        # If only one player left, set status back to waiting
        if len(room["players"]) == 1:
            room["status"] = "waiting"
        
        return {"message": "Left room", "room_id": req.room_id, "room": room}
    
    return {"message": "User not in room"}

@app.get("/rooms")
def list_rooms():
    # return a safe summary of rooms
    summary = {
        rid: {"name": r["name"], "players": r["players"], "status": r["status"]}
        for rid, r in rooms.items()
    }
    return {"rooms": summary}

@app.get("/room/{room_id}")
def get_room(room_id: str):
    room = rooms.get(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room