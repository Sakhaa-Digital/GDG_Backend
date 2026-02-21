from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any

class Violation(BaseModel):
    scan_id: Optional[str] = None
    dataset_id: str
    rule_id: str
    row_data: Optional[Dict[str, Any]] = None
    reason: str  # Human-readable explanation of WHY it violated
    severity: str = "medium"
    status: str = "pending"  # pending / reviewed / resolved
    reviewed_by: Optional[str] = None
    created_at: datetime = datetime.utcnow()