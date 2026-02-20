from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
from cloudinary.uploader import upload as cloud_upload
from src.db.db import datasets_collection  # make sure you have this collection
from src.models.dataset import Dataset
from bson import ObjectId
from datetime import datetime

router = APIRouter()


@router.post("/")
async def upload_dataset(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    admin_id: str = "admin123"
):
    temp_path = f"temp_{file.filename}"

    # Save the uploaded file temporarily
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    # Upload to Cloudinary
    result = cloud_upload(
    temp_path,
    folder="datasets",
    resource_type="raw"   # <-- important
    )
    cloud_url = result.get("secure_url")

    # Insert document in MongoDB
    dataset_doc = Dataset(
        name=file.filename,
        uploaded_by=admin_id,
        file_url=cloud_url,
        status="uploaded",
        total_rows=0,
        violations_count=0,
        created_at=datetime.utcnow()
    )

    dataset_insert = await datasets_collection.insert_one(dataset_doc.dict(by_alias=True))

    # 🔥 Optional: background task to process dataset
    # background_tasks.add_task(process_dataset, temp_path, dataset_insert.inserted_id)

    return {
        "message": "Dataset uploaded. Processing started.",
        "dataset_id": str(dataset_insert.inserted_id)
    }


@router.get("/")
async def get_datasets():
    # Fetch all datasets
    cursor = datasets_collection.find({})
    datasets = await cursor.to_list(length=None)

    # Convert ObjectId to string
    for ds in datasets:
        ds["_id"] = str(ds["_id"])

    return {
        "message": "All datasets fetched successfully",
        "datasets": datasets
    }


@router.get("/status/{dataset_id}")
async def get_dataset_status(dataset_id: str):
    dataset = await datasets_collection.find_one({"_id": ObjectId(dataset_id)})
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    return {
        "dataset_id": dataset_id,
        "status": dataset.get("status", "processing"),
        "total_rows": dataset.get("total_rows", 0),
        "violations_count": dataset.get("violations_count", 0)
    }
@router.get("/status")
async def get_all_dataset_status():
    active_datasets = await datasets_collection.find({
        "status": {"$in": ["uploaded", "queued", "scanning", "failed"]}
    }).to_list(length=None)

    results = []

    for ds in active_datasets:
        results.append({
            "dataset_id": str(ds["_id"]),
            "dataset_name": ds.get("name"),
            "status": ds.get("status"),
            "total_rows": ds.get("total_rows", 0),
            "violations_count": ds.get("violations_count", 0),
            "created_at": ds.get("created_at")
        })

    return {"datasets": results}

@router.delete("/{dataset_id}")
async def delete_dataset(dataset_id: str):
    dataset = await datasets_collection.find_one({"_id": ObjectId(dataset_id)})
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    await datasets_collection.delete_one({"_id": ObjectId(dataset_id)})

    return {
        "message": "Dataset deleted successfully",
        "dataset_id": dataset_id
    }
