# src/routes/scan.py
from fastapi import APIRouter, BackgroundTasks, HTTPException
from bson import ObjectId
from datetime import datetime
from src.db.db import datasets_collection, policies_collection, scans_collection,rules_collection
from src.models.scan import Scan
from src.services.scan_service import process_scan  # background task
from src.schemas.scan_schemas import ScanRequest,MultiScanRequest

router = APIRouter()


@router.post("/")
async def scan_dataset(
    scan_request: ScanRequest,
    background_tasks: BackgroundTasks
):
    dataset_id = scan_request.dataset_id

    # 1️⃣ Check if dataset exists
    dataset = await datasets_collection.find_one(
        {"_id": ObjectId(dataset_id)}
    )
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # 2️⃣ Check at least one active policy exists
    active_policy = await policies_collection.find_one({"active": True})
    if not active_policy:
        raise HTTPException(
            status_code=400,
            detail="No active policies found"
        )

    # 3️⃣ Create scan document
    scan_doc = Scan(
        dataset_id=dataset_id,
        status="running"
    )

    # result = await scans_collection.insert_one(
    #     scan_doc.dict(by_alias=True)
    # )
    result = await scans_collection.insert_one(scan_doc.dict(exclude_none=True))

    # Get the ObjectId of inserted scan
    scan_id = result.inserted_id  # ⚡ This is already ObjectId

    # 4️⃣ Start background scanning
    background_tasks.add_task(
        process_scan,
        str(dataset["_id"]),  # pass as str, convert back in process_scan
        str(scan_id)
    )

    return {
        "message": "Scan started",
        "scan_id": str(scan_id)
    }
    
    
@router.post("/batch-scan")
async def batch_scan_datasets(
    request: MultiScanRequest,
    background_tasks: BackgroundTasks
):
    results = []

    for dataset_id in request.dataset_ids:
        # Validate dataset exists
        dataset = await datasets_collection.find_one({"_id": ObjectId(dataset_id)})
        if not dataset:
            results.append({
                "dataset_id": dataset_id,
                "status": "failed",
                "message": "Dataset not found"
            })
            continue

        # Create scan document
        scan_doc = Scan(
            dataset_id=dataset_id,
            status="running",
            scanned_by=request.scanned_by,
            started_at=datetime.utcnow()
        )
        inserted = await scans_collection.insert_one(scan_doc.dict(exclude_none=True))
        scan_id = inserted.inserted_id

        # Add background task
        background_tasks.add_task(process_scan, dataset_id, str(scan_id))

        results.append({
            "dataset_id": dataset_id,
            "status": "queued",
            "scan_id": str(scan_id)
        })

    return {
        "message": "Batch scans started",
        "results": results
    }
    

@router.get("/status")
async def get_scan_status():
    # 1️⃣ Find scans that are queued or running
    active_scans = await scans_collection.find({
        "status": {"$in": ["queued", "running"]}
    }).to_list(length=None)

    results = []
    for scan in active_scans:
        dataset = await datasets_collection.find_one({"_id": ObjectId(scan["dataset_id"])})
        results.append({
            "dataset_id": scan["dataset_id"],
            "dataset_name": dataset.get("name") if dataset else "Unknown",
            "status": scan["status"]
        })

    return {"active_scans": results}

@router.post("/preview-mapping")
async def preview_column_mapping(scan_request: ScanRequest):
    """
    Preview how rule fields will map to CSV columns
    before running the actual scan. Useful for validation.
    """
    import httpx
    import csv
    import io
    from src.services.column_matcher import match_columns_to_fields

    dataset = await datasets_collection.find_one({"_id": ObjectId(scan_request.dataset_id)})
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Download CSV and read headers only
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(dataset["file_url"])

    content = response.content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    csv_columns = reader.fieldnames or []

    # Get all active rules
    policies = await policies_collection.find({"active": True}).to_list(length=None)
    policy_ids = [p["_id"] for p in policies]
    rules = await rules_collection.find({
        "policy_id": {"$in": policy_ids},
        "active": True
    }).to_list(length=None)

    # Collect all rule fields
    all_fields = set()
    for rule in rules:
        for condition in (rule.get("conditions") or []):
            if condition.get("field"):
                all_fields.add(condition["field"])

    # Run semantic matching
    mapping = await match_columns_to_fields(csv_columns, list(all_fields))

    # Build human-readable preview
    preview = []
    for field in all_fields:
        matched_col = mapping.get(field)
        preview.append({
            "rule_field": field,
            "matched_csv_column": matched_col,
            "status": "matched" if matched_col else "no_match",
            "warning": None if matched_col else f"No CSV column found for '{field}' — violations for rules using this field will be skipped"
        })

    return {
        "dataset_name": dataset.get("name"),
        "csv_columns": csv_columns,
        "total_rules": len(rules),
        "field_mappings": preview,
        "unmatched_fields": [p["rule_field"] for p in preview if p["status"] == "no_match"]
    }