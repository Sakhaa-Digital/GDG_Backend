from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()

mongodb_url = os.getenv("MONGODB_URI")         # e.g., mongodb://localhost:27017
mongodb_name = os.getenv("MONGODB_NAME")       # e.g., SmartPolicy

client = AsyncIOMotorClient(mongodb_url)
db = client[mongodb_name]                      # select your database

# optional: create collection shortcuts
policies_collection = db["policies"]          # now you can do await policies_collection.insert_one(...)
rules_collection = db["rules"]              # for storing extracted rules
policy_chunks_collection=db['policy_chunks']
users_collection=db['user']