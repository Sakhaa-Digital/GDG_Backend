# # src/services/scan_service.py
# import csv
# import httpx
# from bson import ObjectId
# from datetime import datetime
# from src.db.db import (
#     datasets_collection,
#     policies_collection,
#     rules_collection,
#     violations_collection,
#     scans_collection
# )


# async def process_scan(dataset_id: str, scan_id: str):
#     try:
#         # Ensure ObjectIds
#         dataset_obj_id = ObjectId(dataset_id)
#         scan_obj_id = ObjectId(scan_id)

#         # 1️⃣ Get dataset
#         dataset = await datasets_collection.find_one({"_id": dataset_obj_id})
#         if not dataset:
#             await scans_collection.update_one(
#                 {"_id": scan_obj_id},
#                 {"$set": {"status": "failed", "completed_at": datetime.utcnow()}}
#             )
#             return

#         file_url = dataset["file_url"]

#         # 2️⃣ Download CSV locally
#         async with httpx.AsyncClient() as client:
#             response = await client.get(file_url)

#         temp_file = f"temp_scan_{scan_id}.csv"
#         with open(temp_file, "wb") as f:
#             f.write(response.content)

#         # 3️⃣ Get all active policies
#         policies = await policies_collection.find({"active": True}).to_list(length=None)
#         policy_ids = [p["_id"] for p in policies]

#         # 4️⃣ Get all active rules for these policies
#         rules = await rules_collection.find({
#             "policy_id": {"$in": policy_ids},
#             "active": True
#         }).to_list(length=None)

#         total_rows = 0
#         violations_count = 0
#         bulk_violations = []

#         # 5️⃣ Stream CSV and check rules
#         with open(temp_file, "r", encoding="utf-8") as f:
#             reader = csv.DictReader(f)
#             for row in reader:
#                 total_rows += 1
#                 for rule in rules:
#                     conditions = rule.get("conditions", [])
#                     if not conditions:
#                         continue
#                     condition = conditions[0]

#                     field = condition.get("field")
#                     operator = condition.get("operator")
#                     value = condition.get("value")

#                     if field not in row:
#                         continue

#                     try:
#                         row_value = float(row[field])
#                     except ValueError:
#                         continue

#                     violated = False
#                     if operator == ">":
#                         violated = row_value > float(value)
#                     elif operator == "<":
#                         violated = row_value < float(value)
#                     elif operator == "=":
#                         violated = row_value == float(value)

#                     if violated:
#                         violations_count += 1
#                         bulk_violations.append({
#                             "scan_id": scan_obj_id,
#                             "dataset_id": dataset_obj_id,
#                             "rule_id": rule["_id"],
#                             "row_data": row,
#                             "severity": rule.get("severity", "medium"),
#                             "status": "pending",
#                             "created_at": datetime.utcnow()
#                         })

#                 # Bulk insert every 1000
#                 if len(bulk_violations) >= 1000:
#                     await violations_collection.insert_many(bulk_violations)
#                     bulk_violations = []

#         # Insert remaining violations
#         if bulk_violations:
#             await violations_collection.insert_many(bulk_violations)

#         # 6️⃣ Update scan status
#         await scans_collection.update_one(
#             {"_id": scan_obj_id},
#             {"$set": {
#                 "status": "completed",
#                 "total_rows_scanned": total_rows,
#                 "violations_found": violations_count,
#                 "completed_at": datetime.utcnow()
#             }}
#         )

#     except Exception as e:
#         # ⚠️ Update scan status as failed
#         await scans_collection.update_one(
#             {"_id": ObjectId(scan_id)},
#             {"$set": {
#                 "status": "failed",
#                 "completed_at": datetime.utcnow()
#             }}
#         )

# src/services/scan_service.py
import csv
import httpx
from bson import ObjectId
from datetime import datetime
from src.db.db import (
    datasets_collection,
    policies_collection,
    rules_collection,
    violations_collection,
    scans_collection
)

async def process_scan(dataset_id: str, scan_id: str):
    scan_obj_id = ObjectId(scan_id)
    dataset_obj_id = ObjectId(dataset_id)

    # ⚡ Mark dataset and scan as running
    await scans_collection.update_one(
        {"_id": scan_obj_id},
        {"$set": {"status": "running", "started_at": datetime.utcnow()}}
    )
    await datasets_collection.update_one(
        {"_id": dataset_obj_id},
        {"$set": {"status": "running"}}
    )

    try:
        # 1️⃣ Get dataset
        dataset = await datasets_collection.find_one({"_id": dataset_obj_id})
        if not dataset:
            await scans_collection.update_one(
                {"_id": scan_obj_id},
                {"$set": {"status": "failed", "completed_at": datetime.utcnow()}}
            )
            await datasets_collection.update_one(
                {"_id": dataset_obj_id},
                {"$set": {"status": "failed"}}
            )
            return

        file_url = dataset["file_url"]

        # 2️⃣ Download CSV locally
        async with httpx.AsyncClient() as client:
            response = await client.get(file_url)

        temp_file = f"temp_scan_{scan_id}.csv"
        with open(temp_file, "wb") as f:
            f.write(response.content)

        # 3️⃣ Get active policies & rules
        policies = await policies_collection.find({"active": True}).to_list(length=None)
        policy_ids = [p["_id"] for p in policies]
        rules = await rules_collection.find({
            "policy_id": {"$in": policy_ids},
            "active": True
        }).to_list(length=None)

        total_rows = 0
        violations_count = 0
        bulk_violations = []

        # 4️⃣ Stream CSV and check rules
        with open(temp_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_rows += 1
                for rule in rules:
                    conditions = rule.get("conditions", [])
                    if not conditions:
                        continue
                    condition = conditions[0]

                    field = condition.get("field")
                    operator = condition.get("operator")
                    value = condition.get("value")

                    if field not in row:
                        continue

                    try:
                        row_value = float(row[field])
                    except ValueError:
                        continue

                    violated = False
                    if operator == ">":
                        violated = row_value > float(value)
                    elif operator == "<":
                        violated = row_value < float(value)
                    elif operator == "=":
                        violated = row_value == float(value)

                    if violated:
                        violations_count += 1
                        bulk_violations.append({
                            "scan_id": scan_obj_id,
                            "dataset_id": dataset_obj_id,
                            "rule_id": rule["_id"],
                            "row_data": row,
                            "severity": rule.get("severity", "medium"),
                            "status": "pending",
                            "created_at": datetime.utcnow()
                        })

                if len(bulk_violations) >= 1000:
                    await violations_collection.insert_many(bulk_violations)
                    bulk_violations = []

        if bulk_violations:
            await violations_collection.insert_many(bulk_violations)

        # 5️⃣ Update scan & dataset as completed
        await scans_collection.update_one(
            {"_id": scan_obj_id},
            {"$set": {
                "status": "completed",
                "total_rows_scanned": total_rows,
                "violations_found": violations_count,
                "completed_at": datetime.utcnow()
            }}
        )
        await datasets_collection.update_one(
            {"_id": dataset_obj_id},
            {"$set": {"status": "completed"}}
        )

    except Exception as e:
        await scans_collection.update_one(
            {"_id": scan_obj_id},
            {"$set": {"status": "failed", "completed_at": datetime.utcnow()}}
        )
        await datasets_collection.update_one(
            {"_id": dataset_obj_id},
            {"$set": {"status": "failed"}}
        )