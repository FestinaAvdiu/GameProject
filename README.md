# Distributed Two-Person Game System

A distributed Rock-Paper-Scissors game implementation featuring a microservices architecture with WebSocket-based real-time gameplay. The system consists of three backend microservices and three client applications across different platforms.

## Project Overview

This project demonstrates a modern distributed system architecture where multiple microservices communicate via HTTP, while clients connect through WebSocket for real-time game interactions. Players can create rooms, join games, and play Rock-Paper-Scissors in a turn-based format with best-of-three scoring.

---

## Technology Summary

### Backend Microservices

| Service | Technology | Port | Description |
|---------|-----------|------|-------------|
| **User Service** | Python (FastAPI 0.109.0) | 8001 | User authentication and management |
| **Room Service** | Python (FastAPI 0.109.0) | 8002 | Game room creation and player matching |
| **Game Rules Service** | Python (FastAPI 0.109.0) | 8003 | Game logic and WebSocket communication |

**Additional Backend Dependencies:**
- `uvicorn==0.27.0` - ASGI server
- `httpx==0.26.0` - HTTP client for service-to-service communication
- `pydantic==2.5.3` - Data validation
- `websockets==12.0` - WebSocket support

### Client Applications

| Client | Technology | Description |
|--------|-----------|-------------|
| **CLI Client** | Python (asyncio, websockets, requests) | Command-line interface for terminal-based gameplay |
| **Web Client** | HTML5, CSS3, JavaScript (Vanilla) | Browser-based application with responsive UI |
| **Mobile Client** | Capacitor 6.x (Android) | Hybrid mobile app wrapping the web client |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         CLIENTS                              │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐          │
│  │   CLI    │      │   Web    │      │  Mobile  │          │
│  │  Client  │      │  Client  │      │  Client  │          │
│  └────┬─────┘      └────┬─────┘      └────┬─────┘          │
└───────┼──────────────────┼──────────────────┼───────────────┘
        │                  │                  │
        │ HTTP (Auth/Room) │                  │
        │ WebSocket (Game) │                  │
        │                  │                  │
┌───────┴──────────────────┴──────────────────┴───────────────┐
│                    MICROSERVICES                             │
│                                                               │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐       │
│  │    User     │◄──┤    Room     │◄──┤    Game     │       │
│  │   Service   │   │   Service   │   │    Rules    │       │
│  │             │   │             │   │   Service   │       │
│  │  Port 8001  │   │  Port 8002  │   │  Port 8003  │       │
│  └─────────────┘   └─────────────┘   └─────────────┘       │
│         │                  │                  │              │
│         └──────HTTP────────┴──────HTTP────────┘              │
└───────────────────────────────────────────────────────────────┘
```

---

## Service-to-Service APIs (HTTP)

All microservices communicate with each other using REST APIs over HTTP.

### 1. Room Service → User Service

**Purpose:** Verify user existence before allowing room operations

#### `GET /users/{username}`

**Description:** Retrieve user information to validate user exists

**Request:**
```http
GET http://localhost:8001/users/alice
```

**Response (200 OK):**
```json
{
  "username": "alice"
}
```

**Response (404 Not Found):**
```json
{
  "detail": "User not found"
}
```

**Used By:**
- Room creation (verify creator exists)
- Room joining (verify joiner exists)

---

### 2. Room Service → Game Rules Service

**Purpose:** Notify Game Rules Service to initialize game state when room is full

#### `POST /start`

**Description:** Initialize a new game when two players have joined a room

**Request:**
```http
POST http://localhost:8003/start
Content-Type: application/json

{
  "room_id": "abc12345",
  "players": ["alice", "bob"]
}
```

**Response (200 OK):**
```json
{
  "message": "Game initialized",
  "game": {
    "room_id": "abc12345",
    "players": ["alice", "bob"],
    "round": 1,
    "moves": {},
    "scores": {
      "alice": 0,
      "bob": 0
    },
    "current_turn": "alice",
    "status": "waiting_for_moves"
  }
}
```

**Triggered When:**
- Second player joins a room
- Room status changes from "waiting" to "playing"

---

### 3. Game Rules Service → Room Service

**Purpose:** Reset room after game ends and all players disconnect

#### `POST /reset_room/{room_id}`

**Description:** Clear players from room and set status back to "waiting" for reuse

**Request:**
```http
POST http://localhost:8002/reset_room/abc12345
```

**Response (200 OK):**
```json
{
  "message": "Room reset and ready for new players",
  "room_id": "abc12345",
  "room": {
    "name": "Game Room 1",
    "players": [],
    "status": "waiting"
  }
}
```

**Triggered When:**
- Both players disconnect from WebSocket
- Game Service cleans up game state

---

## Client-Server APIs (HTTP)

Clients use HTTP REST APIs for authentication and room management operations.

### User Service Endpoints

#### `POST /users/login`

**Description:** Login or auto-register a user

**Request:**
```json
{
  "username": "alice"
}
```

**Response:**
```json
{
  "message": "User 'alice' logged in successfully"
}
```

---

#### `POST /register`

**Description:** Register a new user

**Request:**
```json
{
  "username": "alice"
}
```

**Response:**
```json
{
  "message": "User alice registered successfully"
}
```

---

#### `GET /users`

**Description:** List all registered users

**Response:**
```json
{
  "users": ["alice", "bob", "charlie"]
}
```

---

### Room Service Endpoints

#### `POST /create_room`

**Description:** Create a new game room

**Request:**
```json
{
  "room_name": "Alice's Game",
  "creator": "alice"
}
```

**Response:**
```json
{
  "room_id": "abc12345",
  "room": {
    "name": "Alice's Game",
    "players": ["alice"],
    "status": "waiting"
  }
}
```

---

#### `POST /join_room`

**Description:** Join an existing room

**Request:**
```json
{
  "room_id": "abc12345",
  "username": "bob"
}
```

**Response:**
```json
{
  "room_id": "abc12345",
  "room": {
    "name": "Alice's Game",
    "players": ["alice", "bob"],
    "status": "playing"
  }
}
```

---

#### `GET /rooms`

**Description:** List all available rooms

**Response:**
```json
{
  "rooms": {
    "abc12345": {
      "name": "Alice's Game",
      "players": ["alice"],
      "status": "waiting"
    },
    "def67890": {
      "name": "Bob's Room",
      "players": ["bob", "charlie"],
      "status": "playing"
    }
  }
}
```

---

#### `POST /leave_room`

**Description:** Remove a player from a room

**Request:**
```json
{
  "room_id": "abc12345",
  "username": "alice"
}
```

**Response:**
```json
{
  "message": "Left room",
  "room_id": "abc12345",
  "room": {
    "name": "Alice's Game",
    "players": [],
    "status": "waiting"
  }
}
```

---

## Client-Server APIs (WebSocket)

Real-time game communication happens through WebSocket connections to the Game Rules Service.

### WebSocket Connection

**Endpoint:** `ws://localhost:8003/ws/{room_id}/{username}`

**Example:** `ws://localhost:8003/ws/abc12345/alice`

---

### Message Format

All WebSocket messages use JSON format:

```json
{
  "type": "message_type",
  "field1": "value1",
  "field2": "value2"
}
```

---

## WebSocket Messages: Client → Server

### 1. Make Move

**Description:** Player submits their move for the current round

**Message:**
```json
{
  "type": "move",
  "move": "rock"
}
```

**Fields:**
- `type`: Always `"move"`
- `move`: One of `"rock"`, `"paper"`, or `"scissors"`

**Validation:**
- Must be player's turn
- Move must be valid (rock/paper/scissors)
- Player must be in the game

---

## WebSocket Messages: Server → Client

### 1. Player Joined

**Description:** Notification when a player connects to the game

**Message:**
```json
{
  "type": "player_joined",
  "message": "alice joined the room",
  "username": "alice"
}
```

**Fields:**
- `type`: `"player_joined"`
- `message`: Human-readable notification
- `username`: Username of player who joined

**Sent When:**
- Player establishes WebSocket connection
- Sent to all players in the room

---

### 2. Game Start

**Description:** Both players connected, game is beginning

**Message:**
```json
{
  "type": "game_start",
  "message": "Both players connected! Game starting...",
  "round": 1,
  "players": ["alice", "bob"]
}
```

**Fields:**
- `type`: `"game_start"`
- `message`: Human-readable notification
- `round`: Current round number (always 1 at start)
- `players`: Array of player usernames

**Sent When:**
- Second player connects to the game
- Sent to both players

---

### 3. Your Turn

**Description:** It's this player's turn to make a move

**Message:**
```json
{
  "type": "your_turn",
  "message": "It's your turn!",
  "round": 1
}
```

**Fields:**
- `type`: `"your_turn"`
- `message`: Human-readable notification
- `round`: Current round number (optional)

**Sent When:**
- Game starts (to first player)
- After opponent makes their move
- Start of new round

---

### 4. Waiting

**Description:** Waiting for opponent to make their move

**Message:**
```json
{
  "type": "waiting",
  "message": "Waiting for alice to make their move...",
  "current_player": "alice"
}
```

**Fields:**
- `type`: `"waiting"`
- `message`: Human-readable notification
- `current_player`: Username of player whose turn it is

**Sent When:**
- Game starts (to second player)
- After player makes their move (to that player)

---

### 5. Move Made

**Description:** A player has submitted their move

**Message:**
```json
{
  "type": "move_made",
  "message": "alice made their move",
  "username": "alice"
}
```

**Fields:**
- `type`: `"move_made"`
- `message`: Human-readable notification
- `username`: Player who made the move

**Sent When:**
- Player submits a valid move
- Sent to all players in the room

**Note:** The actual move choice is not revealed until both players have moved

---

### 6. Round Result

**Description:** Both players have moved, showing round outcome

**Message:**
```json
{
  "type": "round_result",
  "round": 1,
  "moves": {
    "alice": "rock",
    "bob": "scissors"
  },
  "winner": "alice",
  "result": "alice wins",
  "scores": {
    "alice": 1,
    "bob": 0
  }
}
```

**Fields:**
- `type`: `"round_result"`
- `round`: Round number that just completed
- `moves`: Object mapping username to their move
- `winner`: Username of round winner, or `null` for draw
- `result`: Human-readable result (`"alice wins"`, `"bob wins"`, or `"draw"`)
- `scores`: Current game scores (first to 2 wins)

**Sent When:**
- Both players have submitted moves
- Sent to all players simultaneously

**Game Rules:**
- Rock beats Scissors
- Scissors beats Paper
- Paper beats Rock
- Same move = Draw (no points awarded)

---

### 7. New Round

**Description:** Starting the next round after a round result

**Message:**
```json
{
  "type": "new_round",
  "message": "Round 2 starting!",
  "round": 2,
  "scores": {
    "alice": 1,
    "bob": 0
  }
}
```

**Fields:**
- `type`: `"new_round"`
- `message`: Human-readable notification
- `round`: New round number
- `scores`: Current game scores

**Sent When:**
- After round result is shown
- Before either player has reached 2 points
- Followed immediately by `your_turn` and `waiting` messages

---

### 8. Game Over

**Description:** A player has won the game (first to 2 points)

**Message:**
```json
{
  "type": "game_over",
  "message": "alice wins the game!",
  "winner": "alice",
  "final_scores": {
    "alice": 2,
    "bob": 1
  }
}
```

**Fields:**
- `type`: `"game_over"`
- `message`: Human-readable notification
- `winner`: Username of game winner
- `final_scores`: Final score breakdown

**Sent When:**
- A player reaches 2 points (wins 2 rounds)
- Game status changes to "finished"

**After This Message:**
- Players can disconnect at their convenience
- Room remains available for reuse
- When both players disconnect, room is automatically reset

---

### 9. Error

**Description:** An error occurred with the player's action

**Message:**
```json
{
  "type": "error",
  "message": "Not your turn! Waiting for bob"
}
```

**Fields:**
- `type`: `"error"`
- `message`: Human-readable error description

**Common Errors:**
- `"Not your turn! Waiting for {username}"` - Player tried to move when it's not their turn
- `"Invalid move! Choose rock, paper, or scissors"` - Player sent invalid move

**Sent When:**
- Player violates game rules
- Sent only to the player who caused the error

---

### 10. Player Left

**Description:** A player disconnected from the game

**Message:**
```json
{
  "type": "player_left",
  "message": "bob disconnected",
  "username": "bob"
}
```

**Fields:**
- `type`: `"player_left"`
- `message`: Human-readable notification
- `username`: Username of player who left

**Sent When:**
- Player's WebSocket connection closes
- Sent to remaining players in the room

**Room Behavior:**
- If one player leaves: Room stays open, other player sees notification
- If both players leave: Room is automatically reset to "waiting" status

---

## Game Flow Example

Here's a complete game flow showing all WebSocket messages:

```
1. Alice connects to WebSocket
   → All: player_joined (alice)

2. Bob connects to WebSocket
   → All: player_joined (bob)
   → All: game_start (round 1, players: [alice, bob])
   → Alice: your_turn
   → Bob: waiting (current_player: alice)

3. Alice submits move: "rock"
   → All: move_made (alice)
   → Bob: your_turn

4. Bob submits move: "scissors"
   → All: move_made (bob)
   → All: round_result (alice: rock, bob: scissors, winner: alice, scores: {alice: 1, bob: 0})
   → All: new_round (round 2)
   → Alice: your_turn
   → Bob: waiting

5. Alice submits move: "paper"
   → All: move_made (alice)
   → Bob: your_turn

6. Bob submits move: "rock"
   → All: move_made (bob)
   → All: round_result (alice: paper, bob: rock, winner: alice, scores: {alice: 2, bob: 0})
   → All: game_over (winner: alice, final_scores: {alice: 2, bob: 0})

7. Both players disconnect
   → Game Service calls Room Service: POST /reset_room/abc12345
   → Room is reset to "waiting" status, ready for new players
```

---

## Setup and Installation

### Prerequisites

- Python 3.8+
- Node.js 18+ (for mobile client)
- Android Studio (for mobile client development)

### Backend Services

1. **Install Python dependencies:**
```bash
pip install -r docs/requirements.txt
```

2. **Start User Service:**
```bash
cd backend/user_service
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

3. **Start Room Service:**
```bash
cd backend/room_service
uvicorn main:app --host 0.0.0.0 --port 8002 --reload
```

4. **Start Game Rules Service:**
```bash
cd backend/game_rules_service
uvicorn main:app --host 0.0.0.0 --port 8003 --reload
```

### CLI Client

```bash
cd clients/cli_client
python client.py
```

### Web Client

Simply open `clients/web_client/index.html` in a web browser, or use a local server:

```bash
cd clients/web_client
python -m http.server 8080
```

Then visit `http://localhost:8080`

### Mobile Client

1. **Install dependencies:**
```bash
cd clients/mobile_client
npm install
```

2. **Sync Capacitor:**
```bash
npx cap sync
```

3. **Open in Android Studio:**
```bash
npx cap open android
```

4. **Update API URLs** in `www/app.js` to point to your computer's IP address:
```javascript
const USER_SERVICE = 'http://YOUR_IP:8001';
const ROOM_SERVICE = 'http://YOUR_IP:8002';
const GAME_SERVICE = 'ws://YOUR_IP:8003';
```

5. **Build and run** in Android Studio

---

## Project Structure

```
game/
├── backend/
│   ├── user_service/
│   │   └── main.py
│   ├── room_service/
│   │   └── main.py
│   └── game_rules_service/
│       └── main.py
├── clients/
│   ├── cli_client/
│   │   └── client.py
│   ├── web_client/
│   │   ├── index.html
│   │   ├── app.js
│   │   └── style.css
│   └── mobile_client/
│       ├── www/
│       │   ├── index.html
│       │   ├── app.js
│       │   └── style.css
│       ├── capacitor.config.json
│       └── package.json
├── docs/
│   └── requirements.txt
└── README.md
```

---

## Design Decisions

### Why Microservices?

- **Separation of Concerns:** Each service has a single, well-defined responsibility
- **Independent Scaling:** Services can be scaled independently based on load
- **Technology Flexibility:** Each service can use different technologies if needed
- **Fault Isolation:** Failure in one service doesn't bring down the entire system

### Why WebSocket for Gameplay?

- **Real-time Updates:** Instant notification when opponent makes a move
- **Bidirectional Communication:** Server can push updates to clients
- **Persistent Connection:** Reduces overhead compared to polling
- **Low Latency:** Critical for responsive gaming experience

### Why HTTP for Service Communication?

- **Simplicity:** REST APIs are easy to understand and implement
- **Stateless:** No session management needed between services
- **Standard:** Well-supported by all frameworks and libraries
- **Debugging:** Easy to test with tools like curl or Postman

### Room Reusability

Rooms are not deleted after games end - they are reset to "waiting" status. This allows:
- Same room to be reused for multiple games
- Reduced overhead of creating/destroying rooms
- Players can use memorable room IDs

---

## Known Limitations

- **No Persistent Storage:** All data is stored in memory (resets on service restart)
- **No Authentication:** Simple username-based system without passwords
- **No Session Management:** Users can log in from multiple devices simultaneously
- **Single Game Type:** Only Rock-Paper-Scissors is implemented
- **No Reconnection Handling:** Players who disconnect lose their game state

---

## Future Enhancements

- Add persistent database storage (PostgreSQL/MongoDB)
- Implement JWT-based authentication
- Add multiple game types (Tic-Tac-Toe, Connect Four, etc.)
- Implement game history and statistics
- Add spectator mode for watching ongoing games
- Implement reconnection handling
- Add chat functionality between players

---

## Contributors

- Festina Avdiu - University of Pécs, Computer Science Engineering

---

## License

This project is developed as part of a university course assignment.
