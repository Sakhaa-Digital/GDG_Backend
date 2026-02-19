from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class Violation(BaseModel):
    id: Optional[str]
    transaction_id: str
    rule_id: str
    reason: str
    status: str = "pending"  # pending / reviewed
    reviewed_by: Optional[str] = None
    created_at: datetime = datetime.utcnow()
