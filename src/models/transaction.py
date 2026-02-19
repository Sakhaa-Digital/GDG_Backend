from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class Transaction(BaseModel):
    id:Optional[str]
    account_id:str
    amount:float
    created_at:datetime=datetime.now()