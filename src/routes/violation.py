
from fastapi import APIRouter, Query, HTTPException
from src.db.db import violations_collection, rules_collection, policies_collection,datasets_collection,scans_collection
from typing import Optional,List
from datetime import datetime
from collections import defaultdict
from typing import Dict

router = APIRouter()
from bson import ObjectId, errors

# @router.get("/")
# async def get_violations(
#     dataset_id: Optional[str] = None,
#     skip: int = Query(0, ge=0),
#     limit: int = Query(20, ge=1, le=100)
# ):
#     query = {}

#     # Convert dataset_id string to ObjectId
#     if dataset_id:
#         try:
#             query["dataset_id"] = ObjectId(dataset_id)
#         except errors.InvalidId:
#             raise HTTPException(status_code=400, detail="Invalid dataset_id format")

#     cursor = violations_collection.find(query).skip(skip).limit(limit)
#     violations = await cursor.to_list(length=limit)

#     # Serialize ObjectId and datetime
#     def serialize(doc):
#         for key, value in doc.items():
#             if isinstance(value, ObjectId):
#                 doc[key] = str(value)
#             elif isinstance(value, datetime):
#                 doc[key] = value.isoformat()
#         return doc

#     violations_serialized = [serialize(v) for v in violations]

#     total_count = await violations_collection.count_documents(query)

#     return {
#         "violations": violations_serialized,
#         "skip": skip,
#         "limit": limit,
#         "total": total_count,
#         "has_more": skip + limit < total_count
#     }
    

@router.get("/")
async def get_violations(
    dataset_id: Optional[str] = None,
    severity: Optional[str] = Query(None, description="Filter by severity (high, medium, low)"),
    status: Optional[str] = Query(None, description="Filter by violation status (pending, resolved)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    populate_rules: bool = Query(True),
    populate_dataset_scan: bool = Query(True)
):
    query = {}

    # ---------------- FILTERS ----------------
    if dataset_id:
        try:
            query["dataset_id"] = ObjectId(dataset_id)
        except errors.InvalidId:
            raise HTTPException(status_code=400, detail="Invalid dataset_id format")

    if severity:
        query["severity"] = severity.lower()

    if status:
        query["status"] = status.lower()

    # ---------------- FETCH ----------------
    cursor = violations_collection.find(query).skip(skip).limit(limit)
    violations = await cursor.to_list(length=limit)

    results = []
    for v in violations:
        v_serialized = deep_serialize(v)

        # RULE + POLICY POPULATION
        if populate_rules and "rule_id" in v_serialized:
            rule = await rules_collection.find_one({"_id": ObjectId(v_serialized["rule_id"])})
            if rule:
                v_serialized["rule"] = {
                    "rule_id": str(rule["_id"]),
                    "rule_text": rule.get("rule_text"),
                    "severity": rule.get("severity")
                }

                policy = await policies_collection.find_one({"_id": ObjectId(rule.get("policy_id"))})
                v_serialized["policy"] = {
                    "policy_id": str(rule.get("policy_id")),
                    "name": policy.get("name") if policy else None
                }

            v_serialized.pop("rule_id", None)

        # DATASET + SCAN POPULATION
        if populate_dataset_scan:
            if "dataset_id" in v_serialized:
                ds = await datasets_collection.find_one({"_id": ObjectId(v_serialized["dataset_id"])})
                if ds:
                    v_serialized["dataset"] = {
                        "dataset_id": str(ds["_id"]),
                        "name": ds.get("name"),
                        "file_url": ds.get("file_url"),
                        "uploaded_by": ds.get("uploaded_by")
                    }
                v_serialized.pop("dataset_id", None)

            if "scan_id" in v_serialized:
                scan = await scans_collection.find_one({"_id": ObjectId(v_serialized["scan_id"])})
                if scan:
                    v_serialized["scan"] = {
                        "scan_id": str(scan["_id"]),
                        "status": scan.get("status"),
                        "total_rows_scanned": scan.get("total_rows_scanned"),
                        "violations_found": scan.get("violations_found"),
                        "started_at": scan.get("started_at").isoformat() if scan.get("started_at") else None,
                        "completed_at": scan.get("completed_at").isoformat() if scan.get("completed_at") else None
                    }
                v_serialized.pop("scan_id", None)

        results.append(v_serialized)

    total_count = await violations_collection.count_documents(query)

    return {
        "violations": results,
        "skip": skip,
        "limit": limit,
        "total": total_count,
        "has_more": skip + limit < total_count
    }
# @router.get("/")
# async def get_violations(
#     dataset_id: Optional[str] = None,
#     skip: int = Query(0, ge=0),
#     limit: int = Query(20, ge=1, le=100),
#     populate_rules: bool = Query(True, description="Populate rule & policy info"),
#     populate_dataset_scan: bool = Query(True, description="Populate dataset & scan info")
# ):
#     """
#     Flexible Violations API:
#     - Filters by dataset_id if provided, else returns all datasets
#     - Supports pagination with skip & limit
#     - Populates rule, policy, dataset, and scan info for dashboard display
#     """
#     query = {}
#     if dataset_id:
#         try:
#             query["dataset_id"] = ObjectId(dataset_id)
#         except errors.InvalidId:
#             raise HTTPException(status_code=400, detail="Invalid dataset_id format")

#     # Fetch violations
#     cursor = violations_collection.find(query).skip(skip).limit(limit)
#     violations = await cursor.to_list(length=limit)

#     results = []
#     for v in violations:
#         v_serialized = deep_serialize(v)

#         # -------------------- RULE & POLICY --------------------
#         if populate_rules and "rule_id" in v_serialized:
#             rule = await rules_collection.find_one({"_id": ObjectId(v_serialized["rule_id"])})
#             if rule:
#                 v_serialized["rule"] = {
#                     "rule_id": str(rule["_id"]),
#                     "rule_text": rule.get("rule_text"),
#                     "severity": rule.get("severity")
#                 }
#                 # Fetch policy info
#                 policy = await policies_collection.find_one({"_id": ObjectId(rule.get("policy_id"))})
#                 v_serialized["policy"] = {
#                     "policy_id": str(rule.get("policy_id")),
#                     "name": policy.get("name") if policy else None
#                 }
#             v_serialized.pop("rule_id", None)  # remove raw id

#         # -------------------- DATASET & SCAN --------------------
#         if populate_dataset_scan:
#             # Dataset info
#             if "dataset_id" in v_serialized:
#                 ds = await datasets_collection.find_one({"_id": ObjectId(v_serialized["dataset_id"])})
#                 if ds:
#                     v_serialized["dataset"] = {
#                         "dataset_id": str(ds["_id"]),
#                         "name": ds.get("name"),
#                         "file_url": ds.get("file_url"),
#                         "uploaded_by": ds.get("uploaded_by")
#                     }
#                 v_serialized.pop("dataset_id", None)

#             # Scan info
#             if "scan_id" in v_serialized:
#                 scan = await scans_collection.find_one({"_id": ObjectId(v_serialized["scan_id"])})
#                 if scan:
#                     v_serialized["scan"] = {
#                         "scan_id": str(scan["_id"]),
#                         "status": scan.get("status"),
#                         "total_rows_scanned": scan.get("total_rows_scanned"),
#                         "violations_found": scan.get("violations_found"),
#                         "started_at": scan.get("started_at").isoformat() if scan.get("started_at") else None,
#                         "completed_at": scan.get("completed_at").isoformat() if scan.get("completed_at") else None
#                     }
#                 v_serialized.pop("scan_id", None)

#         results.append(v_serialized)

#     total_count = await violations_collection.count_documents(query)

#     return {
#         "violations": results,
#         "skip": skip,
#         "limit": limit,
#         "total": total_count,
#         "has_more": skip + limit < total_count
#     }


# async def get_violations(
#     dataset_id: Optional[str] = None,
#     skip: int = Query(0, ge=0),
#     limit: int = Query(20, ge=1, le=100),
#     populate_rules: bool = Query(False, description="If true, populate rule & policy info")
# ):
#     """
#     Flexible Violations API:
#     - If dataset_id provided → filter by dataset
#     - If dataset_id not provided → return all datasets
#     - Supports lazy loading via skip & limit
#     - Optional rule & policy info population
#     """
#     query = {}
    
#     # Apply dataset filter if provided
#     if dataset_id:
#         try:
#             query["dataset_id"] = ObjectId(dataset_id)
#         except errors.InvalidId:
#             raise HTTPException(status_code=400, detail="Invalid dataset_id format")

#     # Fetch violations with pagination
#     cursor = violations_collection.find(query).skip(skip).limit(limit)
#     violations = await cursor.to_list(length=limit)

#     violations_serialized = []

#     for v in violations:
#         v = deep_serialize(v)

#         # Populate rule and policy info if requested
#         if populate_rules and "rule_id" in v:
#             rule = await rules_collection.find_one({"_id": ObjectId(v["rule_id"])})
#             if rule:
#                 v["rule_text"] = rule.get("rule_text")
#                 v["rule_severity"] = rule.get("severity")
#                 policy = await policies_collection.find_one({"_id": ObjectId(rule.get("policy_id"))})
#                 v["policy_name"] = policy.get("name") if policy else None

#         violations_serialized.append(v)

#     total_count = await violations_collection.count_documents(query)

#     return {
#         "violations": violations_serialized,
#         "skip": skip,
#         "limit": limit,
#         "total": total_count,
#         "has_more": skip + limit < total_count
#     }
    
    
# def serialize(doc: dict):
#     """Convert ObjectId and datetime to str for JSON serialization."""
#     for key, value in doc.items():
#         if isinstance(value, ObjectId):
#             doc[key] = str(value)
#         elif isinstance(value, datetime):
#             doc[key] = value.isoformat()
#     return doc

def deep_serialize(obj):
    """
    Recursively convert ObjectId and datetime to string for JSON.
    Works on dicts, lists, nested structures.
    """
    if isinstance(obj, dict):
        return {k: deep_serialize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [deep_serialize(v) for v in obj]
    elif isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    else:
        return obj

@router.get("/dashboard-stats")
async def dashboard_stats():
    """
    Dashboard-level statistics:
    - Total violations
    - Total datasets with violations
    - Total rules violated
    - Total policies impacted
    - Severity breakdown
    """

    # 1️⃣ Fetch all violations
    all_violations = await violations_collection.find().to_list(length=None)

    total_violations = len(all_violations)
    severity_count: Dict[str, int] = defaultdict(int)
    datasets_count: Dict[str, int] = defaultdict(int)
    rules_count: Dict[str, int] = defaultdict(int)
    policies_count: Dict[str, int] = defaultdict(int)

    for v in all_violations:
        # Count severity
        sev = v.get("severity")
        if sev:
            severity_count[sev] += 1

        # Count dataset
        dataset_id = str(v.get("dataset_id"))
        datasets_count[dataset_id] += 1

        # Count rule
        rule_id = str(v.get("rule_id"))
        rules_count[rule_id] += 1

    # Count policies affected via rules
    rule_ids = list(rules_count.keys())
    if rule_ids:
        # Fetch rules to get policy_ids
        rules = await rules_collection.find({"_id": {"$in": [ObjectId(rid) for rid in rule_ids]}}).to_list(length=None)
        for rule in rules:
            policy_id = str(rule.get("policy_id"))
            if policy_id:
                policies_count[policy_id] += rules_count[str(rule["_id"])]

    # Fetch dataset names
    dataset_names = {}
    if datasets_count:
        datasets = await datasets_collection.find({"_id": {"$in": [ObjectId(did) for did in datasets_count.keys()]}}).to_list(length=None)
        for ds in datasets:
            dataset_names[str(ds["_id"])] = ds.get("name")

    # Fetch policy names
    policy_names = {}
    if policies_count:
        policies = await policies_collection.find({"_id": {"$in": [ObjectId(pid) for pid in policies_count.keys()]}}).to_list(length=None)
        for p in policies:
            policy_names[str(p["_id"])] = p.get("name")

    return {
        "total_violations": total_violations,
        "severity_summary": dict(severity_count),
        "datasets_summary": {dataset_names.get(k, k): v for k, v in datasets_count.items()},
        "rules_summary": {k: v for k, v in rules_count.items()},
        "policies_summary": {policy_names.get(k, k): v for k, v in policies_count.items()},
    }