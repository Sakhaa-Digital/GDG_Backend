# src/routes/scan.py
from fastapi import APIRouter, BackgroundTasks, HTTPException
from bson import ObjectId
from datetime import datetime
from src.db.db import datasets_collection, policies_collection, scans_collection
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