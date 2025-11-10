"""
Database Schemas for Tennis Club App

Each Pydantic model name maps to a MongoDB collection with the lowercase name.
Example: class User -> collection "user"
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime

# Core
class User(BaseModel):
    email: EmailStr
    name: str
    role: Literal["player", "admin"] = "player"
    rating: Optional[int] = Field(default=1200, ge=200, le=3000, description="Elo-like rating")
    level: Optional[Literal["beginner", "intermediate", "advanced", "pro"]] = "beginner"
    bio: Optional[str] = ""
    avatar_url: Optional[str] = None
    preferences: dict = Field(default_factory=lambda: {"language": "en", "notifications": True})

class Court(BaseModel):
    name: str
    surface: Literal["hard", "clay", "grass", "carpet"] = "hard"
    indoor: bool = False
    is_active: bool = True

class Booking(BaseModel):
    user_id: str
    court_id: str
    start_time: datetime
    end_time: datetime
    status: Literal["confirmed", "cancelled"] = "confirmed"

class Equipment(BaseModel):
    name: str
    category: Literal["racket", "balls", "machine", "other"] = "other"
    quantity: int = Field(ge=0, default=1)
    notes: Optional[str] = None

class GearReservation(BaseModel):
    user_id: str
    equipment_id: str
    start_time: datetime
    end_time: datetime
    status: Literal["reserved", "returned", "cancelled"] = "reserved"

class Tournament(BaseModel):
    title: str
    level: Optional[str] = None
    start_date: datetime
    end_date: datetime
    description: Optional[str] = None
    participants: List[str] = Field(default_factory=list)

class MatchResult(BaseModel):
    player1_id: str
    player2_id: str
    winner_id: str
    tournament_id: Optional[str] = None
    played_at: datetime
    score: str

class Event(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None

class RSVP(BaseModel):
    user_id: str
    event_id: str
    status: Literal["going", "interested", "not_going"] = "going"

class ChatRoom(BaseModel):
    name: str
    type: Literal["group", "tournament", "team"] = "group"
    members: List[str] = Field(default_factory=list)
    admins: List[str] = Field(default_factory=list)

class Message(BaseModel):
    room_id: str
    sender_id: str
    content: str
    type: Literal["text", "system"] = "text"

class Notification(BaseModel):
    user_id: str
    title: str
    message: str
    type: Literal["info", "success", "warning", "error"] = "info"
    is_read: bool = False
