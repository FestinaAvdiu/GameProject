from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List
import json
import httpx

app = FastAPI(title="Game Rules Service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOM_SERVICE_URL = "http://localhost:8002"

# In-memory storage
connections: Dict[str, Dict[str, WebSocket]] = {}
games: Dict[str, Dict] = {}

class StartGameReq(BaseModel):
    room_id: str
    players: List[str]

@app.post("/start")
def start_game(req: StartGameReq):
    """Called by Room Service when 2 players join a room"""
    if req.room_id in games:
        return {"message": "Game already exists"}
    
    games[req.room_id] = {
        "room_id": req.room_id,
        "players": req.players,
        "round": 1,
        "moves": {},
        "scores": {req.players[0]: 0, req.players[1]: 0},
        "current_turn": req.players[0],
        "status": "waiting_for_moves"
    }
    
    return {"message": "Game initialized", "game": games[req.room_id]}

@app.websocket("/ws/{room_id}/{username}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, username: str):
    await websocket.accept()
    
    if room_id not in connections:
        connections[room_id] = {}
    connections[room_id][username] = websocket
    
    await broadcast_to_room(room_id, {
        "type": "player_joined",
        "message": f"{username} joined the room",
        "username": username
    })
    
    if room_id in games:
        game = games[room_id]
        if len(connections[room_id]) == 2:
            await broadcast_to_room(room_id, {
                "type": "game_start",
                "message": "Both players connected! Game starting...",
                "round": game["round"]
            })
            
            await send_to_player(room_id, game["current_turn"], {
                "type": "your_turn",
                "message": "It's your turn!",
                "round": game["round"]
            })
            
            other_player = [p for p in game["players"] if p != game["current_turn"]][0]
            await send_to_player(room_id, other_player, {
                "type": "waiting",
                "message": f"Waiting for {game['current_turn']} to make their move...",
                "current_player": game["current_turn"]
            })
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "move":
                await handle_move(room_id, username, message.get("move"))
                
    except WebSocketDisconnect:
        if room_id in connections and username in connections[room_id]:
            del connections[room_id][username]
        
        await broadcast_to_room(room_id, {
            "type": "player_left",
            "message": f"{username} disconnected",
            "username": username
        })

async def handle_move(room_id: str, username: str, move: str):
    if room_id not in games:
        return
    
    game = games[room_id]
    
    if game["current_turn"] != username:
        await send_to_player(room_id, username, {
            "type": "error",
            "message": f"Not your turn! Waiting for {game['current_turn']}"
        })
        return
    
    if move not in ["rock", "paper", "scissors"]:
        await send_to_player(room_id, username, {
            "type": "error",
            "message": "Invalid move! Choose rock, paper, or scissors"
        })
        return
    
    game["moves"][username] = move
    
    await broadcast_to_room(room_id, {
        "type": "move_made",
        "message": f"{username} made their move",
        "username": username
    })
    
    if len(game["moves"]) == 2:
        await evaluate_round(room_id)
    else:
        other_player = [p for p in game["players"] if p != username][0]
        game["current_turn"] = other_player
        
        await send_to_player(room_id, other_player, {
            "type": "your_turn",
            "message": "It's your turn!"
        })

async def evaluate_round(room_id: str):
    game = games[room_id]
    players = game["players"]
    moves = game["moves"]
    
    p1, p2 = players[0], players[1]
    move1, move2 = moves[p1], moves[p2]
    
    winner = None
    if move1 == move2:
        result = "draw"
    elif (move1 == "rock" and move2 == "scissors") or \
         (move1 == "scissors" and move2 == "paper") or \
         (move1 == "paper" and move2 == "rock"):
        winner = p1
        game["scores"][p1] += 1
        result = f"{p1} wins"
    else:
        winner = p2
        game["scores"][p2] += 1
        result = f"{p2} wins"
    
    await broadcast_to_room(room_id, {
        "type": "round_result",
        "round": game["round"],
        "moves": {p1: move1, p2: move2},
        "winner": winner,
        "result": result,
        "scores": game["scores"]
    })
    
    if game["scores"][p1] == 2 or game["scores"][p2] == 2:
        overall_winner = p1 if game["scores"][p1] == 2 else p2
        await broadcast_to_room(room_id, {
            "type": "game_over",
            "message": f"{overall_winner} wins the game!",
            "winner": overall_winner,
            "final_scores": game["scores"]
        })
        game["status"] = "finished"
        
        try:
            httpx.post(f"{ROOM_SERVICE_URL}/reset_room/{room_id}", timeout=3.0)
            print(f"Room {room_id} reset for new game")
        except Exception as e:
            print(f"Could not reset room {room_id}: {e}")
        
        if room_id in games:
            del games[room_id]
        if room_id in connections:
            del connections[room_id]
    else:
        game["round"] += 1
        game["moves"] = {}
        game["current_turn"] = players[0]
        
        await broadcast_to_room(room_id, {
            "type": "new_round",
            "message": f"Round {game['round']} starting!",
            "round": game["round"],
            "scores": game["scores"]
        })
        
        await send_to_player(room_id, players[0], {
            "type": "your_turn",
            "message": "It's your turn!",
            "round": game["round"]
        })
        
        await send_to_player(room_id, players[1], {
            "type": "waiting",
            "message": f"Waiting for {players[0]} to make their move...",
            "current_player": players[0]
        })

async def broadcast_to_room(room_id: str, message: dict):
    if room_id not in connections:
        return
    
    for username, ws in connections[room_id].items():
        try:
            await ws.send_json(message)
        except:
            pass

async def send_to_player(room_id: str, username: str, message: dict):
    if room_id in connections and username in connections[room_id]:
        try:
            await connections[room_id][username].send_json(message)
        except:
            pass

@app.get("/game/{room_id}")
def get_game_state(room_id: str):
    if room_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    return games[room_id]

@app.get("/health")
def health_check():
    return {"status": "healthy", "active_games": len(games)}