from pydantic import BaseModel

class ScanRequest(BaseModel):
    dataset_id: str
    
# src/schemas/scan_schemas.py
# from pydantic import BaseModel
from typing import List

class MultiScanRequest(BaseModel):
    dataset_ids: List[str]
    scanned_by: str  # optional, if you want to track who started the scans