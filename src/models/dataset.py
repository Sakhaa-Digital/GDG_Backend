from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId

# Simple helper for ObjectId
class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema):
        return {"type": "string", "pattern": "^[0-9a-fA-F]{24}$"}

# Dataset model
class Dataset(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    name: str
    file_url: str
    uploaded_by: str
    status: str = "processing"
    total_rows: int = 0
    violations_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
