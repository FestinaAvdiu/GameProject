from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="User Service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory user storage (acts like a temporary database)
users = {}

# Define a User data model (for request validation)
class User(BaseModel):
    username: str

class LoginRequest(BaseModel):
    username: str

# Register a user
@app.post("/register")
def register_user(user: User):
    if user.username in users:
        return {"message": "Username already exists"}
    users[user.username] = {"username": user.username}
    return {"message": f"User {user.username} registered successfully"}

# Login endpoint
@app.post("/users/login")
def login_user(request: LoginRequest):
    username = request.username
    if username in users:
        return {"message": f"User '{username}' logged in successfully"}
    # If user doesn't exist, auto-register them
    users[username] = {"username": username}
    return {"message": f"User '{username}' registered and logged in successfully"}

# List users
@app.get("/users")
def get_users():
    return {"users": list(users.keys())}

# For checking a single user - Room service will use this
@app.get("/users/{username}")
def get_user(username: str):
    """
    Retrieve a single user by username.
    Returns 200 + user info if found, 404 if not found.
    """
    user = users.get(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
