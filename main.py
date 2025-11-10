import os
from datetime import datetime, timedelta
from typing import List, Optional, Literal, Dict, Any

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

from database import db, create_document, get_documents

app = FastAPI(title="Tennis Club API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Auth & Role (simplified demo)
# -----------------------------
class LoginRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    role: Literal["player", "admin"] = "player"

class LoginResponse(BaseModel):
    token: str
    role: str
    user_id: str

# naive in-memory token map for demo (OK since tokens are ephemeral). Real apps should use JWT.
TOKENS: Dict[str, Dict[str, Any]] = {}

def get_current_user(token: str) -> Dict[str, Any]:
    if token not in TOKENS:
        raise HTTPException(status_code=401, detail="Invalid token")
    return TOKENS[token]

@app.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    # Upsert user by email
    from bson import ObjectId
    existing = list(db.user.find({"email": payload.email}).limit(1)) if db else []
    if existing:
        user = existing[0]
    else:
        from schemas import User
        user_model = User(email=payload.email, name=payload.name or payload.email.split("@")[0], role=payload.role)
        _id = create_document("user", user_model)
        user = db.user.find_one({"_id": ObjectId(_id)})
    # set/override role if provided
    if payload.role and user.get("role") != payload.role:
        db.user.update_one({"_id": user["_id"]}, {"$set": {"role": payload.role}})
        user["role"] = payload.role

    token = f"tok_{str(user['_id'])}"
    TOKENS[token] = {"user_id": str(user["_id"]), "role": user.get("role", "player"), "email": user["email"], "name": user.get("name")}
    return LoginResponse(token=token, role=TOKENS[token]["role"], user_id=TOKENS[token]["user_id"])

@app.get("/me")
def me(token: str):
    return get_current_user(token)

# -----------------------------
# Courts & Booking
# -----------------------------
class CourtIn(BaseModel):
    name: str
    surface: Literal["hard", "clay", "grass", "carpet"] = "hard"
    indoor: bool = False

class BookingIn(BaseModel):
    court_id: str
    start_time: datetime
    end_time: datetime

@app.post("/admin/courts")
def create_court(payload: CourtIn, token: str):
    user = get_current_user(token)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    _id = create_document("court", payload.model_dump())
    return {"id": _id}

@app.get("/courts")
def list_courts():
    return get_documents("court")

@app.post("/bookings")
def create_booking(payload: BookingIn, token: str):
    _ = get_current_user(token)
    # naive conflict check
    from bson import ObjectId
    overlap = list(db.booking.find({
        "court_id": payload.court_id,
        "$or": [
            {"start_time": {"$lt": payload.end_time}, "end_time": {"$gt": payload.start_time}}
        ]
    }))
    if overlap:
        raise HTTPException(status_code=400, detail="Court already booked for that time")
    data = payload.model_dump()
    data["user_id"] = _["user_id"]
    _id = create_document("booking", data)
    return {"id": _id}

@app.get("/my/bookings")
def my_bookings(token: str):
    u = get_current_user(token)
    return get_documents("booking", {"user_id": u["user_id"]})

# -----------------------------
# Tournaments & Results
# -----------------------------
class TournamentIn(BaseModel):
    title: str
    level: Optional[str] = None
    start_date: datetime
    end_date: datetime
    description: Optional[str] = None

@app.post("/admin/tournaments")
def create_tournament(payload: TournamentIn, token: str):
    user = get_current_user(token)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    _id = create_document("tournament", payload.model_dump())
    return {"id": _id}

@app.get("/tournaments")
def list_tournaments():
    return get_documents("tournament")

class ResultIn(BaseModel):
    player1_id: str
    player2_id: str
    winner_id: str
    score: str
    tournament_id: Optional[str] = None
    played_at: datetime

@app.post("/results")
def submit_result(payload: ResultIn, token: str):
    _ = get_current_user(token)
    _id = create_document("matchresult", payload.model_dump())
    return {"id": _id}

@app.get("/leaderboard")
def leaderboard(level: Optional[str] = None, limit: int = 50):
    flt = {"role": "player"}
    if level:
        flt["level"] = level
    players = list(db.user.find(flt, {"name": 1, "rating": 1, "level": 1}).sort("rating", -1).limit(limit))
    for p in players:
        p["_id"] = str(p["_id"])  # stringify
    return players

# -----------------------------
# Players directory / profiles
# -----------------------------
@app.get("/players")
def player_directory(q: Optional[str] = None, level: Optional[str] = None, limit: int = 50):
    flt: Dict[str, Any] = {"role": "player"}
    if level:
        flt["level"] = level
    if q:
        flt["name"] = {"$regex": q, "$options": "i"}
    users = list(db.user.find(flt, {"name": 1, "level": 1, "rating": 1, "avatar_url": 1}).limit(limit))
    for u in users:
        u["_id"] = str(u["_id"])  # stringify
    return users

# -----------------------------
# AI Assistants (stubbed to use OPENAI_API_KEY if present)
# -----------------------------
class ChatRequest(BaseModel):
    role: Literal["coach", "club"] = "coach"
    message: str
    context: Optional[Dict[str, Any]] = None

@app.post("/ai/chat")
def ai_chat(req: ChatRequest, token: Optional[str] = None):
    # very lightweight proxy. If OPENAI_API_KEY absent, return heuristic tip
    import os
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        tip = "Work on consistent footwork, keep your head still through contact, and practice cross-court rally drills for control."
        if req.role == "club":
            tip = "Courts are less busy early mornings. Check tournaments in the events tab and book 48h ahead for best availability."
        return {"answer": tip}
    try:
        import requests
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        prompt = f"You are a concise tennis {req.role} assistant. Keep answers under 80 words. User: {req.message} Context: {req.context or {}}"
        body = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}]}
        resp = requests.post("https://api.openai.com/v1/chat/completions", json=body, headers=headers, timeout=20)
        data = resp.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "Sorry, no response.")
        return {"answer": text}
    except Exception as e:
        return {"answer": "Temporary AI service issue. Try again later.", "error": str(e)[:100]}

# -----------------------------
# Health / Misc
# -----------------------------
@app.get("/")
def root():
    return {"message": "Tennis Club API running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os as _os
    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
