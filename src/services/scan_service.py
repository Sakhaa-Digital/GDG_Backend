# src/services/scan_service.py
import csv
import httpx
import os
from bson import ObjectId
from datetime import datetime
from src.db.db import (
    datasets_collection,
    policies_collection,
    rules_collection,
    violations_collection,
    scans_collection
)
from src.services.column_matcher import match_columns_to_fields


def evaluate_condition(row_value: float, operator: str, rule_value) -> bool:
    """Evaluate a single condition against a row value."""
    try:
        rule_val = float(rule_value)
    except (TypeError, ValueError):
        return False

    ops = {
        ">": row_value > rule_val,
        "<": row_value < rule_val,
        ">=": row_value >= rule_val,
        "<=": row_value <= rule_val,
        "=": row_value == rule_val,
        "!=": row_value != rule_val,
    }
    return ops.get(operator, False)


def evaluate_string_condition(row_value: str, operator: str, rule_value) -> bool:
    """Evaluate string-based conditions."""
    row_val = str(row_value).strip().lower()
    rule_val = str(rule_value).strip().lower()

    if operator == "contains":
        return rule_val in row_val
    elif operator == "not_contains":
        return rule_val not in row_val
    elif operator == "=":
        return row_val == rule_val
    elif operator == "!=":
        return row_val != rule_val
    return False


async def build_column_mapping(csv_columns: list[str], rules: list[dict]) -> dict[str, str]:
    """
    Build a global column mapping for all rule fields in this scan.
    Returns: { rule_field -> csv_column }
    """
    # Collect all unique fields from all rules
    all_fields = set()
    for rule in rules:
        conditions = rule.get("conditions") or []
        for condition in conditions:
            field = condition.get("field")
            if field:
                all_fields.add(field)

    if not all_fields:
        return {}

    mapping = await match_columns_to_fields(csv_columns, list(all_fields))
    return mapping


def check_row_against_rule(row: dict, rule: dict, col_mapping: dict) -> tuple[bool, str]:
    """
    Check if a row violates a rule.
    Returns (violated: bool, reason: str)
    """
    conditions = rule.get("conditions") or []
    if not conditions:
        return False, ""

    violated_reasons = []

    for condition in conditions:
        field = condition.get("field")
        operator = condition.get("operator")
        value = condition.get("value")

        if not field or not operator:
            continue

        # Get matched CSV column
        csv_col = col_mapping.get(field)
        if not csv_col or csv_col not in row:
            continue

        raw_value = row[csv_col]

        # Try numeric evaluation first
        try:
            row_value = float(raw_value)
            violated = evaluate_condition(row_value, operator, value)
            if violated:
                violated_reasons.append(
                    f"Field '{csv_col}' (mapped from '{field}') value {row_value} "
                    f"violates rule: {field} {operator} {value}"
                )
        except (ValueError, TypeError):
            # Fall back to string evaluation
            violated = evaluate_string_condition(str(raw_value), operator, value)
            if violated:
                violated_reasons.append(
                    f"Field '{csv_col}' (mapped from '{field}') value '{raw_value}' "
                    f"violates rule: {field} {operator} {value}"
                )

    if violated_reasons:
        return True, " | ".join(violated_reasons)
    return False, ""


async def process_scan(dataset_id: str, scan_id: str):
    scan_obj_id = ObjectId(scan_id)
    dataset_obj_id = ObjectId(dataset_id)

    await scans_collection.update_one(
        {"_id": scan_obj_id},
        {"$set": {"status": "running", "started_at": datetime.utcnow()}}
    )
    await datasets_collection.update_one(
        {"_id": dataset_obj_id},
        {"$set": {"status": "scanning"}}
    )

    try:
        # 1. Get dataset
        dataset = await datasets_collection.find_one({"_id": dataset_obj_id})
        if not dataset:
            await _mark_failed(scan_obj_id, dataset_obj_id)
            return

        file_url = dataset["file_url"]

        # 2. Download CSV
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(file_url)

        temp_file = f"temp_scan_{scan_id}.csv"
        with open(temp_file, "wb") as f:
            f.write(response.content)

        # 3. Get active rules
        policies = await policies_collection.find({"active": True}).to_list(length=None)
        policy_ids = [p["_id"] for p in policies]

        rules = await rules_collection.find({
            "policy_id": {"$in": policy_ids},
            "active": True
        }).to_list(length=None)

        if not rules:
            await _mark_completed(scan_obj_id, dataset_obj_id, 0, 0)
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return

        # 4. Read CSV headers and build column mapping ONCE
        with open(temp_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            csv_columns = reader.fieldnames or []

        print(f"[Scan] CSV columns: {csv_columns}")

        # 🔑 Build semantic column mapping once for all rules
        col_mapping = await build_column_mapping(csv_columns, rules)
        print(f"[Scan] Column mapping: {col_mapping}")

        total_rows = 0
        violations_count = 0
        bulk_violations = []

        # 5. Stream CSV and check rules
        with open(temp_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_rows += 1

                for rule in rules:
                    violated, reason = check_row_against_rule(row, rule, col_mapping)

                    if violated:
                        violations_count += 1
                        bulk_violations.append({
                            "scan_id": scan_obj_id,
                            "dataset_id": dataset_obj_id,
                            "rule_id": rule["_id"],
                            "row_data": dict(row),
                            "reason": reason,  # 🔑 Human-readable explanation
                            "severity": rule.get("severity", "medium"),
                            "status": "pending",
                            "created_at": datetime.utcnow()
                        })

                # Batch insert every 500
                if len(bulk_violations) >= 500:
                    await violations_collection.insert_many(bulk_violations)
                    bulk_violations = []

        # Insert remaining
        if bulk_violations:
            await violations_collection.insert_many(bulk_violations)

        # 6. Cleanup and update status
        if os.path.exists(temp_file):
            os.remove(temp_file)

        await _mark_completed(scan_obj_id, dataset_obj_id, total_rows, violations_count)

    except Exception as e:
        print(f"[Scan ERROR] {e}")
        if os.path.exists(f"temp_scan_{scan_id}.csv"):
            os.remove(f"temp_scan_{scan_id}.csv")
        await _mark_failed(scan_obj_id, dataset_obj_id)


async def _mark_completed(scan_obj_id, dataset_obj_id, total_rows, violations_count):
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
        {"$set": {
            "status": "completed",
            "total_rows": total_rows,
            "violations_count": violations_count
        }}
    )


async def _mark_failed(scan_obj_id, dataset_obj_id):
    await scans_collection.update_one(
        {"_id": scan_obj_id},
        {"$set": {"status": "failed", "completed_at": datetime.utcnow()}}
    )
    await datasets_collection.update_one(
        {"_id": dataset_obj_id},
        {"$set": {"status": "failed"}}
    )