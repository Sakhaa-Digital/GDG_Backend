from beanie import Document
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime

# -----------------------------
# 1️⃣ User Document for MongoDB
# -----------------------------
class User(Document):
    uid: str = Field(..., unique=True)  # Google UID, required
    role: str = Field(default="user", regex="^(user|admin)$")
    name: str = Field(..., min_length=1)
    email: EmailStr = Field(..., unique=True)
    picture: Optional[str] = None
    provider: str = Field(default="google")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "users"  # MongoDB collection name

    # class Config:
    #     schema_extra = {
    #         "example": {
    #             "uid": "1234567890",
    #             "role": "user",
    #             "name": "Bishal Kumar Adhikari",
    #             "email": "bishal@example.com",
    #             "picture": "https://example.com/pic.png",
    #             "provider": "google"
    #         }
    #     }
