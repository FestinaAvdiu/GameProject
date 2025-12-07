const USER_SERVICE = 'http://10.0.2.2:8001';
const ROOM_SERVICE = 'http://10.0.2.2:8002';
const GAME_SERVICE = 'ws://10.0.2.2:8003';

let username = '';
let currentRoomId = '';
let ws = null;
let gameState = {
    players: [],
    scores: {},
    round: 1
};

function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(screenId).classList.add('active');
}

function showError(elementId, message) {
    const el = document.getElementById(elementId);
    el.innerHTML = `<div class="error">${message}</div>`;
    setTimeout(() => el.innerHTML = '', 3000);
}

async function login() {
    const input = document.getElementById('usernameInput').value.trim();
    if (!input) {
        showError('loginError', 'Please enter a username');
        return;
    }

    try {
        const response = await fetch(`${USER_SERVICE}/users/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: input })
        });

        if (response.ok) {
            username = input;
            document.getElementById('usernameDisplay').textContent = username;
            showMenu();
        } else {
            showError('loginError', 'Login failed. Please try again.');
        }
    } catch (error) {
        showError('loginError', 'Cannot connect to server');
    }
}

function logout() {
    username = '';
    currentRoomId = '';
    if (ws) ws.close();
    document.getElementById('usernameInput').value = ''; // Clear input field
    showScreen('loginScreen');
}

function showMenu() {
    showScreen('menuScreen');
}

function showCreateRoom() {
    document.getElementById('roomNameInput').value = ''; // Clear previous room name
    showScreen('createRoomScreen');
}

function showJoinRoom() {
    document.getElementById('roomIdInput').value = ''; // Clear previous room ID
    showScreen('joinRoomScreen');
}

async function createRoom() {
    const roomName = document.getElementById('roomNameInput').value.trim();
    if (!roomName) {
        showError('createRoomError', 'Please enter a room name');
        return;
    }

    try {
        const response = await fetch(`${ROOM_SERVICE}/create_room`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ room_name: roomName, creator: username })
        });

        const data = await response.json();
        if (response.ok) {
            currentRoomId = data.room_id;
            document.getElementById('currentRoomId').textContent = currentRoomId;
            connectWebSocket();
            showScreen('waitingScreen');
        } else {
            showError('createRoomError', data.detail || 'Failed to create room');
        }
    } catch (error) {
        showError('createRoomError', 'Cannot connect to server');
    }
}

async function joinRoomById() {
    const roomId = document.getElementById('roomIdInput').value.trim();
    if (!roomId) {
        showError('joinRoomError', 'Please enter a room ID');
        return;
    }

    await joinRoom(roomId);
}

async function joinRoom(roomId) {
    try {
        const response = await fetch(`${ROOM_SERVICE}/join_room`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ room_id: roomId, username: username })
        });

        const data = await response.json();
        if (response.ok) {
            currentRoomId = roomId;
            document.getElementById('currentRoomId').textContent = currentRoomId;
            
            // Check if room already has 2 players (game starting immediately)
            const room = data.room;
            if (room.players.length === 2) {
                // Game will start, go to game screen
                connectWebSocket();
                showScreen('gameScreen');
                clearGameUI(); // Clear any previous game state
            } else {
                // Waiting for second player
                connectWebSocket();
                showScreen('waitingScreen');
            }
        } else {
            showError('joinRoomError', data.detail || 'Failed to join room');
        }
    } catch (error) {
        showError('joinRoomError', 'Cannot connect to server');
    }
}

async function showRoomList() {
    try {
        const response = await fetch(`${ROOM_SERVICE}/rooms`);
        const data = await response.json();
        const rooms = data.rooms;

        const roomListEl = document.getElementById('roomList');
        
        if (Object.keys(rooms).length === 0) {
            roomListEl.innerHTML = '<div class="no-rooms">No rooms available. Create one!</div>';
        } else {
            roomListEl.innerHTML = '';
            for (const [roomId, room] of Object.entries(rooms)) {
                if (room.status === 'waiting') {
                    const roomDiv = document.createElement('div');
                    roomDiv.className = 'room-item';
                    roomDiv.onclick = () => joinRoom(roomId);
                    roomDiv.innerHTML = `
                        <h3>${room.name}</h3>
                        <p>Players: ${room.players.length}/2 (${room.players.join(', ')})</p>
                        <p>Room ID: ${roomId}</p>
                    `;
                    roomListEl.appendChild(roomDiv);
                }
            }
        }

        showScreen('roomListScreen');
    } catch (error) {
        alert('Cannot fetch rooms');
    }
}

function connectWebSocket() {
    const wsUrl = `${GAME_SERVICE}/ws/${currentRoomId}/${username}`;
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log('WebSocket connected');
        // Clear message log when connecting to a new game
        document.getElementById('messageLog').innerHTML = '';
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleGameMessage(data);
    };

    ws.onclose = () => {
        console.log('WebSocket closed');
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        addMessage('Connection error', 'system');
    };
}

function clearGameUI() {
    // Don't clear message log - keep player joined messages
    // Only reset game state elements
    
    // Reset status message
    document.getElementById('gameStatus').textContent = 'Waiting...';
    
    // Reset scores
    document.getElementById('player1Name').textContent = 'Player 1';
    document.getElementById('player1Score').textContent = '0';
    document.getElementById('player2Name').textContent = 'Player 2';
    document.getElementById('player2Score').textContent = '0';
    
    // Hide move buttons
    document.getElementById('movesContainer').style.display = 'none';
    
    // Reset game state
    gameState = {
        players: [],
        scores: {},
        round: 1
    };
}

function handleGameMessage(data) {
    const type = data.type;

    if (type === 'player_joined') {
        addMessage(data.message, 'system');
        
        // If we're on waiting screen and another player joins, stay there
        // The game_start message will move us to game screen
    } else if (type === 'game_start') {
        // Clear any previous game state and move to game screen
        clearGameUI();
        showScreen('gameScreen');
        addMessage(data.message, 'system');
        gameState.round = data.round;
        
        // Set player names if available
        if (data.players && data.players.length === 2) {
            gameState.players = data.players;
            document.getElementById('player1Name').textContent = data.players[0];
            document.getElementById('player2Name').textContent = data.players[1];
        }
    } else if (type === 'your_turn') {
        document.getElementById('gameStatus').textContent = "🎯 Your turn! Choose your move:";
        document.getElementById('movesContainer').style.display = 'flex';
    } else if (type === 'waiting') {
        document.getElementById('gameStatus').textContent = `⏳ ${data.message}`;
        document.getElementById('movesContainer').style.display = 'none';
    } else if (type === 'move_made') {
        if (data.username === username) {
            // Don't show "you made your move" message
        } else {
            addMessage(`${data.username} made their move`, 'system');
            document.getElementById('gameStatus').textContent = `⏳ Waiting for ${data.username} to finish...`;
        }
    } else if (type === 'round_result') {
        document.getElementById('movesContainer').style.display = 'none';
        
        // Create visual move display
        const moveIcons = {
            'rock': '✊',
            'paper': '✋',
            'scissors': '✌️'
        };
        
        const players = Object.keys(data.moves);
        const movesHtml = `
            <div class="moves-display">
                <div class="player-move">
                    <div class="player-name">${moveIcons[data.moves[players[0]]]} ${players[0]}</div>
                    <div class="move-name">${data.moves[players[0]]}</div>
                </div>
                <div class="player-move">
                    <div class="player-name">${moveIcons[data.moves[players[1]]]} ${players[1]}</div>
                    <div class="move-name">${data.moves[players[1]]}</div>
                </div>
            </div>
        `;
        
        document.getElementById('messageLog').insertAdjacentHTML('beforeend', movesHtml);
        addMessage(`Round ${data.round}: ${data.result}`, 'round-result');
        
        // Update scores
        gameState.scores = data.scores;
        updateScores();
        
        // Scroll to bottom
        document.getElementById('messageLog').scrollTop = document.getElementById('messageLog').scrollHeight;
    } else if (type === 'new_round') {
        addMessage(`Round ${data.round} starting!`, 'system');
        gameState.round = data.round;
    } else if (type === 'game_over') {
        document.getElementById('movesContainer').style.display = 'none';
        
        // Show game over message with leave button
        document.getElementById('gameStatus').innerHTML = `
            <div style="text-align: center;">
                <h2 style="margin-bottom: 15px;">🎉 Game Over!</h2>
                <p style="font-size: 18px; margin-bottom: 20px;">${data.message}</p>
                <button onclick="leaveRoom()" style="width: auto; padding: 12px 30px;">Leave Room</button>
            </div>
        `;
        
        addMessage(`🏆 ${data.message}`, 'winner');
    } else if (type === 'error') {
        addMessage(`❌ ${data.message}`, 'system');
    } else if (type === 'player_left') {
        addMessage(`👋 ${data.message}`, 'system');
        
        // If a player leaves during the game, show option to leave
        document.getElementById('gameStatus').innerHTML = `
            <div style="text-align: center;">
                <h2 style="margin-bottom: 15px;">⚠️ Player Disconnected</h2>
                <p style="font-size: 18px; margin-bottom: 20px;">${data.message}</p>
                <button onclick="leaveRoom()" style="width: auto; padding: 12px 30px;">Leave Room</button>
            </div>
        `;
        document.getElementById('movesContainer').style.display = 'none';
    }
}

function updateScores() {
    const players = Object.keys(gameState.scores);
    if (players.length >= 2) {
        document.getElementById('player1Name').textContent = players[0];
        document.getElementById('player1Score').textContent = gameState.scores[players[0]];
        document.getElementById('player2Name').textContent = players[1];
        document.getElementById('player2Score').textContent = gameState.scores[players[1]];
    }
}

function makeMove(move) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'move', move: move }));
        document.getElementById('movesContainer').style.display = 'none';
        
        // Capitalize move name
        const moveCapitalized = move.charAt(0).toUpperCase() + move.slice(1);
        
        document.getElementById('gameStatus').textContent = `You chose: ${moveCapitalized}. Waiting for opponent...`;
        addMessage(`You chose: ${moveCapitalized}`, 'system');
    }
}

function addMessage(msg, type = 'system') {
    const log = document.getElementById('messageLog');
    const div = document.createElement('div');
    div.className = `message-item ${type}`;
    div.textContent = msg;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
}

function leaveRoom() {
    if (ws) ws.close();
    currentRoomId = '';
    showMenu();
}