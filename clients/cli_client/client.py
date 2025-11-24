import asyncio
import websockets
import json
import requests
import sys

# Service URLs
USER_SERVICE = "http://localhost:8001"
ROOM_SERVICE = "http://localhost:8002"
GAME_SERVICE = "ws://localhost:8003"

class GameClient:
    def __init__(self):
        self.username = None
        self.room_id = None
        self.websocket = None
        self.game_ended = False
        
    def register_user(self, username):
        """Register a new user"""
        try:
            response = requests.post(f"{USER_SERVICE}/register", json={"username": username})
            if response.status_code == 200:
                print(f"✅ Registered as {username}")
                self.username = username
                return True
            else:
                print(f"⚠️  {response.json().get('message', 'Registration failed')}")
                return False
        except Exception as e:
            print(f"❌ Error connecting to User Service: {e}")
            return False
    
    def login_user(self, username):
        """Login existing user"""
        try:
            response = requests.post(f"{USER_SERVICE}/users/login", json={"username": username})
            if response.status_code == 200:
                print(f"✅ Logged in as {username}")
                self.username = username
                return True
            else:
                print(f"⚠️  User not found. Registering...")
                return self.register_user(username)
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def create_room(self, room_name):
        """Create a new game room"""
        try:
            response = requests.post(f"{ROOM_SERVICE}/create_room", 
                                    json={"room_name": room_name, "creator": self.username})
            if response.status_code == 200:
                data = response.json()
                self.room_id = data["room_id"]
                print(f"✅ Room created! Room ID: {self.room_id}")
                print(f"📋 Share this Room ID with another player: {self.room_id}")
                return True
            else:
                print(f"❌ Failed to create room: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def join_room(self, room_id):
        """Join an existing room"""
        try:
            response = requests.post(f"{ROOM_SERVICE}/join_room",
                                    json={"room_id": room_id, "username": self.username})
            if response.status_code == 200:
                self.room_id = room_id
                data = response.json()
                room = data.get("room", {})
                players = room.get("players", [])
                
                print(f"✅ Joined room: {room_id}")
                print(f"👥 Players in room: {', '.join(players)}")
                return True
            else:
                print(f"❌ Failed to join room: {response.json().get('detail', 'Unknown error')}")
                return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    async def connect_websocket(self):
        """Connect to game via WebSocket"""
        uri = f"{GAME_SERVICE}/ws/{self.room_id}/{self.username}"
        print(f"🔌 Connecting to game server...")
        
        try:
            self.websocket = await websockets.connect(uri)
            print(f"✅ Connected to game!")
            print(f"{'='*50}")
            
            # Start listening for messages
            await self.listen_for_messages()
            
        except Exception as e:
            print(f"❌ Connection error: {e}")
        
        # When connection ends, return control to main loop
        return
    
    async def listen_for_messages(self):
        """Listen for messages from server"""
        try:
            async for message in self.websocket:
                data = json.loads(message)
                await self.handle_message(data)
        except websockets.exceptions.ConnectionClosed:
            print("\n❌ Connection closed by server")
        except Exception as e:
            print(f"\n❌ Error: {e}")
    
    async def handle_message(self, data):
        """Handle different types of messages from server"""
        msg_type = data.get("type")
        
        if msg_type == "player_joined":
            print(f"\n👤 {data['message']}")
            
        elif msg_type == "game_start":
            print(f"\n🎮 {data['message']}")
            print(f"📍 Round {data['round']}")
            
        elif msg_type == "your_turn":
            print(f"\n💭 {data['message']}")
            await self.prompt_move()
            
        elif msg_type == "waiting":
            print(f"\n⏳ {data['message']}")
            
        elif msg_type == "move_made":
            print(f"\n✋ {data['message']}")
            
        elif msg_type == "round_result":
            print(f"\n{'='*50}")
            print(f"📊 ROUND {data['round']} RESULTS:")
            print(f"  {list(data['moves'].keys())[0]}: {data['moves'][list(data['moves'].keys())[0]]}")
            print(f"  {list(data['moves'].keys())[1]}: {data['moves'][list(data['moves'].keys())[1]]}")
            print(f"  🏆 {data['result']}")
            print(f"\n📈 Current Scores:")
            for player, score in data['scores'].items():
                print(f"  {player}: {score}")
            print(f"{'='*50}")
            
        elif msg_type == "new_round":
            print(f"\n🔄 {data['message']}")
            # Don't automatically prompt - wait for "your_turn" message
            
        elif msg_type == "game_over":
            print(f"\n{'='*50}")
            print(f"🎉 GAME OVER!")
            print(f"👑 {data['message']}")
            print(f"\n📊 Final Scores:")
            for player, score in data['final_scores'].items():
                print(f"  {player}: {score}")
            print(f"{'='*50}")
            print("\n🔄 Returning to main menu...")
            # Close websocket and return to menu
            await self.websocket.close()
            # Set flag to return to menu
            self.game_ended = True
            return
            
        elif msg_type == "error":
            print(f"\n⚠️  {data['message']}")
            
        elif msg_type == "player_left":
            print(f"\n👋 {data['message']}")
    
    async def prompt_move(self):
        """Prompt user to make a move"""
        print("\n💭 Your turn! Choose your move:")
        print("  1. rock")
        print("  2. paper")
        print("  3. scissors")
        
        # Run input in executor to not block WebSocket
        loop = asyncio.get_event_loop()
        move = await loop.run_in_executor(None, self.get_move_input)
        
        if move:
            await self.send_move(move)
    
    def get_move_input(self):
        """Get move input from user (blocking)"""
        while True:
            choice = input("\nEnter your move: ").strip().lower()
            if choice in ["rock", "paper", "scissors", "1", "2", "3"]:
                if choice == "1":
                    return "rock"
                elif choice == "2":
                    return "paper"
                elif choice == "3":
                    return "scissors"
                return choice
            print("❌ Invalid choice! Please enter rock, paper, or scissors")
    
    async def send_move(self, move):
        """Send move to server"""
        message = {
            "type": "move",
            "move": move
        }
        await self.websocket.send(json.dumps(message))
        print(f"✅ You chose: {move}")

async def main():
    client = GameClient()
    
    print("🎮 Rock-Paper-Scissors Game Client")
    print("="*50)
    
    # Login once
    username = input("Enter your username: ").strip()
    if not client.login_user(username):
        return
    
    # Main game loop - keep playing until user exits
    while True:
        client.room_id = None
        client.websocket = None
        client.game_ended = False
        
        # Room selection menu
        print("\n📂 Room Options:")
        print("  1. Create new room")
        print("  2. Join existing room")
        print("  3. View available rooms")
        print("  4. Log out")
        
        choice = input("\nYour choice (1, 2, 3, or 4): ").strip()
        
        if choice == "4":
            print("\n👋 Thanks for playing! Goodbye!")
            break
        
        if choice == "1":
            room_name = input("Enter room name: ").strip()
            if not client.create_room(room_name):
                continue
            print("\n⏳ Waiting for another player to join...")
        elif choice == "2":
            room_id = input("Enter room ID: ").strip()
            if not client.join_room(room_id):
                continue
        elif choice == "3":
            # Show available rooms
            try:
                response = requests.get(f"{ROOM_SERVICE}/rooms")
                if response.status_code == 200:
                    rooms_data = response.json().get("rooms", {})
                    if not rooms_data:
                        print("\n📭 No rooms available. Create one!")
                        room_name = input("Enter room name: ").strip()
                        if not client.create_room(room_name):
                            continue
                        print("\n⏳ Waiting for another player to join...")
                    else:
                        print("\n📋 Available Rooms:")
                        for room_id, room_info in rooms_data.items():
                            status = room_info.get("status", "unknown")
                            players = room_info.get("players", [])
                            name = room_info.get("name", "Unnamed")
                            player_count = len(players)
                            
                            # Only show rooms that are waiting (not full)
                            if status == "waiting":
                                print(f"  🏠 Room: {name}")
                                print(f"     ID: {room_id}")
                                print(f"     Players: {player_count}/2 ({', '.join(players)})")
                                print()
                        
                        room_choice = input("Enter room ID to join (or 'new' to create): ").strip()
                        if room_choice.lower() == "new":
                            room_name = input("Enter room name: ").strip()
                            if not client.create_room(room_name):
                                continue
                            print("\n⏳ Waiting for another player to join...")
                        else:
                            if not client.join_room(room_choice):
                                continue
                else:
                    print("❌ Could not fetch rooms")
                    continue
            except Exception as e:
                print(f"❌ Error: {e}")
                continue
        else:
            print("❌ Invalid choice")
            continue
        
        # Connect to game
        await client.connect_websocket()
        
        # After game ends, loop back to menu

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)