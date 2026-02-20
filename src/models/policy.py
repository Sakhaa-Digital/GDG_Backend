from pydantic import BaseModel, Field
from typing import List,Optional
from datetime import datetime

class Policy(BaseModel):
    # id:Optional[str] = Field(None, alias="_id")
    name:str
    uploaded_by:str
    file_path:str
    source_type:str #pdf,docs
    active:bool=True
    created_at:datetime=datetime.now()
    original_filename:str
    embedding: Optional[List[float]] = None

    