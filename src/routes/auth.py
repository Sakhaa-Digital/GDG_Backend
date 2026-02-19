from fastapi import FastAPI, HTTPException, Request
from fastapi import APIRouter, UploadFile, File,BackgroundTasks

from pydantic import BaseModel
import firebase_admin
from firebase_admin import credentials, auth
from pymongo import MongoClient
import os
import json
from src.db.db import users_collection

router = APIRouter()

class GoogleAuthRequest(BaseModel):
    token: str

# -----------------------------
# 5️⃣ Google Auth endpoint
# -----------------------------
@router.post("/googleauth")
async def google_auth(data: GoogleAuthRequest):
    try:
        # ✅ Verify Firebase token
        decoded = auth.verify_id_token(data.token)
        uid = decoded.get("uid")
        email = decoded.get("email")
        name = decoded.get("name")
        picture = decoded.get("picture")

        # 🔍 Check if user exists
        user =await users_collection.find_one({"uid": uid})
        if user:
            return {"success": True, "message": f"Welcome {name}", "user": user}

        # ➕ Create new user
        new_user = {
            "uid": uid,
            "name": name,
            "email": email,
            "picture": picture,
            "provider": "google",
            "role":"admin"
        }
        users_collection.insert_one(new_user)

        return {"success": True, "user": new_user}

    except Exception as e:
        print(e)
        raise HTTPException(status_code=401, detail="Invalid or expired token")
