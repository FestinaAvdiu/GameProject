from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from typing import Dict, List
import json
import httpx

app = FastAPI(title="Game Rules Service")

ROOM_SERVICE_URL = "http://localhost:8002"

# In-memory storage
# connections: room_id -> {username: WebSocket}
connections: Dict[str, Dict[str, WebSocket]] = {}

# games: room_id -> {round, moves, scores, players, current_turn}
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
        "current_turn": req.players[0],  # First player goes first
        "status": "waiting_for_moves"
    }
    
    return {"message": "Game initialized", "game": games[req.room_id]}

@app.websocket("/ws/{room_id}/{username}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, username: str):
    await websocket.accept()
    
    # Store connection
    if room_id not in connections:
        connections[room_id] = {}
    connections[room_id][username] = websocket
    
    # Notify other players
    await broadcast_to_room(room_id, {
        "type": "player_joined",
        "message": f"{username} joined the room",
        "username": username
    })
    
    # If game exists and both players connected, start
    if room_id in games:
        game = games[room_id]
        if len(connections[room_id]) == 2:
            await broadcast_to_room(room_id, {
                "type": "game_start",
                "message": "Both players connected! Game starting...",
                "round": game["round"]
            })
            
            # Tell first player it's their turn
            await send_to_player(room_id, game["current_turn"], {
                "type": "your_turn",
                "message": "It's your turn!",
                "round": game["round"]
            })
            
            # Tell second player to wait
            other_player = [p for p in game["players"] if p != game["current_turn"]][0]
            await send_to_player(room_id, other_player, {
                "type": "waiting",
                "message": f"Waiting for {game['current_turn']} to make their move...",
                "current_player": game["current_turn"]
            })
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "move":
                await handle_move(room_id, username, message.get("move"))
                
    except WebSocketDisconnect:
        # Clean up connection
        if room_id in connections and username in connections[room_id]:
            del connections[room_id][username]
        
        await broadcast_to_room(room_id, {
            "type": "player_left",
            "message": f"{username} disconnected",
            "username": username
        })

async def handle_move(room_id: str, username: str, move: str):
    """Process a player's move"""
    if room_id not in games:
        return
    
    game = games[room_id]
    
    # Check if it's this player's turn
    if game["current_turn"] != username:
        await send_to_player(room_id, username, {
            "type": "error",
            "message": f"Not your turn! Waiting for {game['current_turn']}"
        })
        return
    
    # Validate move
    if move not in ["rock", "paper", "scissors"]:
        await send_to_player(room_id, username, {
            "type": "error",
            "message": "Invalid move! Choose rock, paper, or scissors"
        })
        return
    
    # Store the move
    game["moves"][username] = move
    
    # Broadcast that player made a move (WITHOUT revealing what it was)
    await broadcast_to_room(room_id, {
        "type": "move_made",
        "message": f"{username} made their move",
        "username": username
    })
    
    # Check if both players have moved
    if len(game["moves"]) == 2:
        await evaluate_round(room_id)
    else:
        # Switch turn to other player
        other_player = [p for p in game["players"] if p != username][0]
        game["current_turn"] = other_player
        
        await send_to_player(room_id, other_player, {
            "type": "your_turn",
            "message": "It's your turn!"
        })

async def evaluate_round(room_id: str):
    """Determine round winner and update game state"""
    game = games[room_id]
    players = game["players"]
    moves = game["moves"]
    
    p1, p2 = players[0], players[1]
    move1, move2 = moves[p1], moves[p2]
    
    # Determine winner
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
    
    # Send round result
    await broadcast_to_room(room_id, {
        "type": "round_result",
        "round": game["round"],
        "moves": {p1: move1, p2: move2},
        "winner": winner,
        "result": result,
        "scores": game["scores"]
    })
    
    # Check if game is over (best of 3 - first to 2 wins)
    if game["scores"][p1] == 2 or game["scores"][p2] == 2:
        overall_winner = p1 if game["scores"][p1] == 2 else p2
        await broadcast_to_room(room_id, {
            "type": "game_over",
            "message": f"{overall_winner} wins the game!",
            "winner": overall_winner,
            "final_scores": game["scores"]
        })
        game["status"] = "finished"
        
        # Tell Room Service to reset the room status (keep room, clear players)
        try:
            httpx.post(f"{ROOM_SERVICE_URL}/reset_room/{room_id}", timeout=3.0)
            print(f"Room {room_id} reset for new game")
        except Exception as e:
            print(f"Could not reset room {room_id}: {e}")
        
        # Clean up game data
        if room_id in games:
            del games[room_id]
        if room_id in connections:
            del connections[room_id]
    else:
        # Start next round - first player goes first again
        game["round"] += 1
        game["moves"] = {}
        game["current_turn"] = players[0]
        
        await broadcast_to_room(room_id, {
            "type": "new_round",
            "message": f"Round {game['round']} starting!",
            "round": game["round"],
            "scores": game["scores"]
        })
        
        # Tell first player it's their turn
        await send_to_player(room_id, players[0], {
            "type": "your_turn",
            "message": "It's your turn!",
            "round": game["round"]
        })
        
        # Tell second player to wait
        await send_to_player(room_id, players[1], {
            "type": "waiting",
            "message": f"Waiting for {players[0]} to make their move...",
            "current_player": players[0]
        })

async def broadcast_to_room(room_id: str, message: dict):
    """Send message to all players in a room"""
    if room_id not in connections:
        return
    
    for username, ws in connections[room_id].items():
        try:
            await ws.send_json(message)
        except:
            pass  # Connection might be closed

async def send_to_player(room_id: str, username: str, message: dict):
    """Send message to a specific player"""
    if room_id in connections and username in connections[room_id]:
        try:
            await connections[room_id][username].send_json(message)
        except:
            pass

@app.get("/game/{room_id}")
def get_game_state(room_id: str):
    """Get current game state (for debugging)"""
    if room_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    return games[room_id]

@app.get("/health")
def health_check():
    return {"status": "healthy", "active_games": len(games)}