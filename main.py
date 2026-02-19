from fastapi import FastAPI
from src.routes.policies import router as policies_router
from src.routes.auth import router as auth_router
import os
import json
import firebase_admin
from firebase_admin import credentials, auth
from fastapi.middleware.cors import CORSMiddleware


service_account_path = os.path.join(os.getcwd(), "serviceAcc.json")
cred = credentials.Certificate(service_account_path)

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)
app = FastAPI(title="Policy Compliance Hackathon API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # <-- allows all origins
    allow_credentials=True,   # allow cookies, auth headers
    allow_methods=["*"],      # allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],      # allow all headers
)
app.include_router(policies_router, prefix="/policies", tags=["Policies"])
app.include_router(auth_router, prefix="/auth", tags=["Auth"])

@app.get("/")
def hello():
    return {"Hello": "World"}