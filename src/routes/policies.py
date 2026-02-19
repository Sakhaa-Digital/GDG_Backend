from fastapi import APIRouter, UploadFile, File,BackgroundTasks,HTTPException
from cloudinary.uploader import upload as cloud_upload
from src.db.db import policies_collection,rules_collection,policy_chunks_collection
from src.services.extraction import extract_rules, extract_text, generate_embedding,chunk_text,process_policy
from src.models.policy import Policy
from src.utils.cloudinary_config import cloudinary
from bson import ObjectId

router = APIRouter()


@router.post("/")
# async def upload_policy(
#     background_tasks: BackgroundTasks,
#     file: UploadFile = File(...),
#     admin_id: str = "admin123"
# ):
#     temp_path = f"temp_{file.filename}"

#     with open(temp_path, "wb") as f:
#         f.write(await file.read())

#     result = cloud_upload(temp_path, folder="policies")
#     cloud_url = result.get("secure_url")

#     policy_doc = Policy(
#         name=file.filename,
#         uploaded_by=admin_id,
#         file_path=cloud_url,
#         source_type=file.content_type,
#         active=True
#     )

#     policy_insert = await policies_collection.insert_one(policy_doc.dict())

#     # 🔥 Background processing
#     background_tasks.add_task(process_policy, temp_path, policy_insert.inserted_id)

#     return {
#         "message": "Policy uploaded. Processing started.",
#         "policy_id": str(policy_insert.inserted_id)
#     }
async def upload_policy(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    admin_id: str = "admin123"
):
    temp_path = f"temp_{file.filename}"

    # Save the uploaded file temporarily
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    # Upload to cloud (your existing function)
    result = cloud_upload(temp_path, folder="policies")
    cloud_url = result.get("secure_url")

    # Insert document in MongoDB
    policy_doc = Policy(
        name=file.filename,
        uploaded_by=admin_id,
        file_path=cloud_url,
        source_type=file.content_type,
        active=True
    )
    policy_insert = await policies_collection.insert_one(policy_doc.dict())

    # 🔥 Use the new online OCR in background
    background_tasks.add_task(process_policy, temp_path, policy_insert.inserted_id)

    return {
        "message": "Policy uploaded. Processing started.",
        "policy_id": str(policy_insert.inserted_id)
    }
    
    
@router.get('/')
async def get_policy():
    # Fetch all documents
    cursor = policies_collection.find({})
    policies = await cursor.to_list(length=None)

    # Convert ObjectId to string
    for policy in policies:
        policy["_id"] = str(policy["_id"])

    return {
        "message": "All policy fetched Successfully",
        "policies": policies
    }

@router.get('/toggle/{policy_id}')
async def toggle_policy(policy_id:str):
    policy=await policies_collection.find_one({"_id":ObjectId(policy_id)})
    if not policy:
        raise HTTPException(status_code=404,detail="Policy not found")
    
    new_status=not policy.get("active",False)
    await policies_collection.update_one(
        
            {"_id": ObjectId(policy_id)},
            {"$set": {"active": new_status}}
        
    )
    return {
        "message": "Policy toggled successfully",
        "policy_id": policy_id,
        "active": new_status
    }