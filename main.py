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
    session_id: str = None 
    project_id: str = None # New: Associate chat with a project context

class CreateSessionRequest(BaseModel):
    user_id: str
    title: str = "New Chat"
    project_id: str = None # New: Sessions usually belong to a project

class CreateProjectRequest(BaseModel):
    user_id: str
    name: str # e.g. "Meditation"
    parent_id: str = None # UUID of parent project. None = Root (but triggers handle roots usually)
    description: str = None

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



from core.memory_manager import memory_manager

# 8️⃣ Main chat route (saves chat history to Supabase)
@app.post("/chat")
def chat(request: ChatRequest):
    # 1. Memory Lifecycle (Routing -> Extraction -> Learning -> Retrieval)
    # The MemoryManager handles the entire lifecycle now.
    context_str = ""
    
    if request.user_id:
        try:
            result = memory_manager.route(
                request.question,
                request.user_id, 
                request.session_id, 
                request.project_id
            )
            context_str = result.get("context", "")
                
        except Exception as e:
            print(f"[Memory Error] Logic failed: {e}")
            # Non-blocking, proceed

    # 4. Chat with LLM (Injecting Context)
    bot_response = bot.chat(request.question, context=context_str)
    
    # NOTE: Extraction is now handled within memory_manager.route() (Step 1 of lifecycle)
    # So we do not need a separate extraction step here.

    # 6. Save Chat History
    if request.user_id:
        try:
            data = {
                "user_id": request.user_id,
                "question": request.question,
                "answer": bot_response
            }
            if request.session_id:
                data["session_id"] = request.session_id
            
            supabase.table("chat_history").insert(data).execute()
        except Exception as e:
            print(f"Error saving chat history: {e}")
            
    return {"answer": bot_response}
            
    return {"answer": bot_response}

# 9️⃣ Session Management Routes

@app.post("/sessions")
def create_session(request: CreateSessionRequest):
    """Creates a new chat session, optionally within a project."""
    try:
        data = {
            "user_id": request.user_id,
            "title": request.title
        }
        if request.project_id:
            data["project_id"] = request.project_id

        res = supabase.table("chat_sessions").insert(data).execute()
        
        # Return the created session
        if res.data:
            return res.data[0]
        else:
            raise HTTPException(status_code=500, detail="Failed to create session")
            
    except Exception as e:
        print("Create session error:", e)
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/sessions/{user_id}")
def get_user_sessions(user_id: str, project_id: str = None):
    """Lists chat sessions. Can filter by project_id."""
    try:
        query = supabase.table("chat_sessions").select("*").eq("user_id", user_id)
        
        if project_id:
            query = query.eq("project_id", project_id)
            
        res = query.order("created_at", desc=True).execute()
        return {"sessions": res.data}
    except Exception as e:
        return {"sessions": [], "error": str(e)}

# 🔟 Get chat history for a SPECIFIC session
@app.get("/history/{session_id}")
def get_session_history(session_id: str):
    try:
        # We now query by session_id instead of user_id for the specific chat view
        res = supabase.table("chat_history").select("*").eq("session_id", session_id).order("timestamp", desc=False).execute() 
        return {"history": res.data}
    except Exception as e:
        return {"history": [], "error": str(e)}

# 11. PROJECT MANAGEMENT (Mind, Body, Soul hierarchical structure)

@app.post("/projects")
def create_project(request: CreateProjectRequest):
    """Creates a new project node in the tree."""
    try:
        data = {
            "user_id": request.user_id,
            "name": request.name,
            "parent_id": request.parent_id, # Can be nested under another project
            "description": request.description
        }
        res = supabase.table("projects").insert(data).execute()
        
        if res.data:
            return res.data[0]
        else:
             raise HTTPException(status_code=500, detail="Failed to create project")
    except Exception as e:
        print("Create project error:", e)
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/projects/{user_id}")
def get_projects(user_id: str, parent_id: str = None):
    """
    Get projects for a user.
    - If parent_id is provided, gets direct children (Sub-projects).
    - If parent_id is NOT provided, gets Root projects (Mind, Body, Soul).
    """
    try:
        query = supabase.table("projects").select("*").eq("user_id", user_id)
        
        if parent_id:
            query = query.eq("parent_id", parent_id)
        else:
             # Get roots (Mind, Body, Soul) -> where parent_id is NULL
             query = query.is_("parent_id", "null")
             
        res = query.order("created_at", desc=True).execute()
        return {"projects": res.data}
    except Exception as e:
        return {"projects": [], "error": str(e)}

@app.get("/projects/tree/{user_id}")
def get_project_tree(user_id: str):
    """
    Experimental: Get full flat list to build tree on frontend.
    """
    try:
        res = supabase.table("projects").select("*").eq("user_id", user_id).execute()
        # Frontend can construct the tree from this flat list using parent_id
        return {"projects": res.data}
    except Exception as e:
         return {"projects": [], "error": str(e)}

# 7️⃣ Reset memory route
@app.post("/reset")
def reset_memory():
    """Clears chatbot short-term memory."""
    bot.reset_memory()
    return {"message": "Chat memory has been reset."}

@app.get("/user/stats/{user_id}")
def get_user_stats(user_id: str):
    """
    Returns AI Knowledge stats: % Optimization, Memory Counts.
    Used for the Dashboard 'Personal Info' bar.
    """
    stats = memory_manager.get_memory_stats(user_id)
    return stats

@app.get("/personal-info/question/{user_id}")
def get_personal_info_question(user_id: str, session_count: int = 0):
    """
    Orchestrator: Returns the next question to ask the user to fill missing memory domains.
    Returns {"question": "...", "domain": "..."} or null if done/limit reached.
    """
    result = memory_manager.get_next_personal_info_question(user_id, session_count)
    return result
