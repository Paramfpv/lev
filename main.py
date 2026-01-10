# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from core.retrieval_pipeline import LongevityRAGChatbot
from core.supabase_utils import supabase

# 1️⃣ Create FastAPI instance
app = FastAPI(title="LEV Longevity RAG API", version="1.0")

# 2️⃣ Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Explicitly allow OPTIONS
    allow_headers=["*"],  # Allow all headers
)

# 3️⃣ Initialize chatbot once (stays in memory)
bot = LongevityRAGChatbot()


# 4️⃣ Define input schemas
class ChatRequest(BaseModel):
    question: str
    user_id: str = None
    session_id: str = None  # Optional for now, but recommended for new chats

class CreateSessionRequest(BaseModel):
    user_id: str
    title: str = "New Chat"

class RegisterRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

# 5️⃣ Default route
@app.get("/")
def root():
    return {
        "message": "LEV RAG API is running.",
        "documentation": "/docs",
        "health_check": "/health"
    }

# 6️⃣ Health Check
@app.get("/health")
def health_check():
    """Checks the status of the API and its dependencies."""
    status = {
        "status": "healthy",
        "database": "unknown",
        "vector_db": "unknown"
    }
    
    # Check Supabase
    try:
        supabase.table("chat_history").select("id").limit(1).execute()
        status["database"] = "connected"
    except Exception as e:
        status["database"] = f"error: {str(e)}"
        status["status"] = "degraded"

    # Check ChromaDB (via bot instance)
    try:
        if bot.client:
            bot.client.heartbeat()
            status["vector_db"] = "connected"
        else:
             status["vector_db"] = "not_initialized"
    except Exception as e:
        status["vector_db"] = f"error: {str(e)}"
        status["status"] = "degraded"

    if status["status"] != "healthy":
        raise HTTPException(status_code=503, detail=status)
        
    return status


# 6️⃣ User registration
# replace register and login implementations with the following

@app.post("/register")
def register(request: RegisterRequest):
    try:
        res = supabase.auth.sign_up({
            "email": request.email,
            "password": request.password
        })

        # Supabase v2 returns an AuthResponse: check res.user (no .error attr)
        if not getattr(res, "user", None):
            # try to return helpful message if available
            detail = getattr(res, "message", None) or getattr(res, "error", None) or "Registration failed"
            raise HTTPException(status_code=400, detail=str(detail))

        return {
            "message": "User registered successfully",
            "user_id": res.user.id,
            "email": res.user.email
        }

    except HTTPException:
        raise
    except Exception as e:
        print("Registration exception:", e)
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/login")
def login(request: LoginRequest):
    try:
        res = supabase.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password
        })

        # If login failed, res.user will be falsy — handle it cleanly
        if not getattr(res, "user", None):
            detail = getattr(res, "message", None) or getattr(res, "error", None) or "Login failed"
            raise HTTPException(status_code=400, detail=str(detail))

        return {
            "message": "Login successful",
            "user_id": res.user.id,
            "email": res.user.email
        }

    except HTTPException:
        raise
    except Exception as e:
        print("Login exception:", e)
        raise HTTPException(status_code=400, detail=str(e))



# 8️⃣ Main chat route (saves chat history to Supabase)
@app.post("/chat")
def chat(request: ChatRequest):
    answer = bot.chat(request.question)
    
    # Save chat to Supabase if user_id provided
    if request.user_id:
        try:
            data = {
                "user_id": request.user_id,
                "question": request.question,
                "answer": answer
            }
            if request.session_id:
                data["session_id"] = request.session_id
                
            supabase.table("chat_history").insert(data).execute()
        except Exception as e:
            print(f"Error saving chat history: {e}")
            
    return {"answer": answer}

# 9️⃣ Session Management Routes

@app.post("/sessions")
def create_session(request: CreateSessionRequest):
    """Creates a new chat session."""
    try:
        res = supabase.table("chat_sessions").insert({
            "user_id": request.user_id,
            "title": request.title
        }).execute()
        
        # Return the created session
        if res.data:
            return res.data[0]
        else:
            raise HTTPException(status_code=500, detail="Failed to create session")
            
    except Exception as e:
        print("Create session error:", e)
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/sessions/{user_id}")
def get_user_sessions(user_id: str):
    """Lists all chat sessions for a user."""
    try:
        res = supabase.table("chat_sessions").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        return {"sessions": res.data}
    except Exception as e:
        return {"sessions": [], "error": str(e)}

# 🔟 Get chat history for a SPECIFIC session
@app.get("/history/{session_id}")
def get_session_history(session_id: str):
    try:
        # We now query by session_id instead of user_id for the specific chat view
        res = supabase.table("chat_history").select("*").eq("session_id", session_id).order("timestamp", desc=False).execute() 
        # Note: Chat UI usually needs ascending order (oldest first), but let's check frontend pref.
        # usually APIs return desc for "recent list" but asc for "conversation view".
        # Let's return ASC so the frontend can just append.
        return {"history": res.data}
    except Exception as e:
        return {"history": [], "error": str(e)}

# 7️⃣ Reset memory route
@app.post("/reset")
def reset_memory():
    """Clears chatbot short-term memory."""
    bot.reset_memory()
    return {"message": "Chat memory has been reset."}
