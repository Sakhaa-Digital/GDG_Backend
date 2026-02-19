from typing import List, Dict, Optional
from pydantic import BaseModel,Field
from datetime import datetime

class Rule(BaseModel):
    id: Optional[str]
    policy_id: str
    rule_text: str
    conditions: Optional[List[Dict]] = None
    severity: str = "medium"
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
