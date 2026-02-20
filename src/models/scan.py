from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class Scan(BaseModel):
    dataset_id: str
    status: str
    total_rows_scanned: int = 0
    violations_found: int = 0
    scanned_by: Optional[str] = None
    started_at: datetime = datetime.utcnow()
    completed_at: Optional[datetime] = None