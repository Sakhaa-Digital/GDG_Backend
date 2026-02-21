# services/extraction.py
import pytesseract  # for image OCR
from pdfminer.high_level import extract_text as pdf_extract
from openai import OpenAI  # or Gemini API if available
from dotenv import load_dotenv
import os
from typing import List, Dict
import re
import json
from src.db.db import policies_collection,rules_collection,policy_chunks_collection
from src.services.imageToText import extract_image_to_text_online
load_dotenv()

# initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def extract_text(file_path: str) -> str:
    """
    Extract text from PDF or Image
    """
    if file_path.lower().endswith(".pdf"):
        text = pdf_extract(file_path)
    elif file_path.lower().endswith((".png", ".jpg", ".jpeg")):
        text = await extract_image_to_text_online(file_path)
    else:
        # assume txt file
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    return text

async def generate_embedding(text: str) -> list:
    """
    Generate embedding using OpenAI / Gemini
    """
    response = client.embeddings.create(
        model="text-embedding-3-small",  # or "gemini-embedding-001"
        input=text
    )
    vector = response.data[0].embedding
    return vector

import re
from typing import List, Dict
def chunk_text(text: str, chunk_size=1200, overlap=150):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks

async def extract_rules(text: str) -> List[Dict]:
    prompt = f"""
You are a compliance rule extraction engine for a data scanning system.

From the policy text below, extract enforceable rules that can be checked against a database/CSV.

For each rule return:
- rule_text: the original sentence
- field: a short snake_case semantic concept name for the data field 
  (e.g. "client_expense", "transaction_amount", "quantity", "account_balance")
  Make this a GENERIC CONCEPT, not tied to any specific column name.
- operator: one of >, <, >=, <=, =, !=, contains, not_contains, is_empty, is_not_empty
- value: the threshold/value (numeric or string), or null
- severity: low, medium, or high
- rule_type: "numeric_threshold" | "string_check" | "null_check" | "process_rule"
- checkable: true if this rule can be checked against data columns, false if it's a process/workflow rule

IMPORTANT: 
- "must not exceed X" → operator: ">", value: X
- "must be at least X" → operator: ">=", value: X  
- "must not be 0" or "must not be empty" → operator: "=", value: 0 (or is_empty)
- "client expense", "spending", "total cost" → field: "client_expense"
- Only return rules where checkable is true

Return ONLY valid JSON array. No explanation.

Policy Text:
{text}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You extract structured compliance rules checkable against tabular data."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    content = response.choices[0].message.content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
    if content.startswith("json"):
        content = content[4:].strip()

    match = re.search(r'\[.*\]', content, re.DOTALL)
    if match:
        rules = json.loads(match.group(0))
        # Only keep checkable rules
        rules = [r for r in rules if r.get("checkable", True)]
    else:
        print("Failed to parse LLM JSON:", content)
        rules = []

    return rules
# async def process_policy(temp_path: str, policy_id):

#     text = await extract_text(temp_path)
#     chunks = chunk_text(text)

#     all_rules = []

#     for chunk in chunks:

#         # 1️⃣ Generate embedding
#         vector = await generate_embedding(chunk)

#         await policy_chunks_collection.insert_one({
#             "policy_id": policy_id,
#             "text": chunk,
#             "embedding": vector
#         })

#         # 2️⃣ Extract rules (ONLY ONCE)
#         rules = await extract_rules(chunk)
#         all_rules.extend(rules)

#     # 3️⃣ Deduplicate rules by rule_text
#     unique = {}
#     for r in all_rules:
#         if "rule_text" in r:
#             unique[r["rule_text"]] = r

#     final_rules = list(unique.values())

#     # 4️⃣ Insert deduplicated rules
#     for rule in final_rules:
#         await rules_collection.insert_one({
#             "policy_id": policy_id,
#             "rule_text": rule["rule_text"],
#             "conditions": [
#                 {
#                     "field": rule.get("field"),
#                     "operator": rule.get("operator"),
#                     "value": rule.get("value")
#                 }
#             ] if rule.get("field") else None,
#             "severity": rule.get("severity", "medium"),
#             "active": True
#         })

#     # 5️⃣ Cleanup
#     os.remove(temp_path)
async def process_policy(temp_path: str, policy_id):
    text = await extract_text(temp_path)
    chunks = chunk_text(text)

    all_rules = []

    for chunk in chunks:
        # 1️⃣ Generate embedding
        vector = await generate_embedding(chunk)

        # store embedding chunk
        await policy_chunks_collection.insert_one({
            "policy_id": policy_id,
            "text": chunk,
            "embedding": vector
        })

        # 2️⃣ Extract structured rules
        rules = await extract_rules(chunk)
        all_rules.extend(rules)

    # Deduplicate rules by rule_text
    unique = {r["rule_text"]: r for r in all_rules if "rule_text" in r}
    final_rules = list(unique.values())

    # Store rules in rules_collection
    for rule in final_rules:
        await rules_collection.insert_one({
            "policy_id": policy_id,
            "rule_text": rule["rule_text"],
            "conditions": [
                {
                    "field": rule.get("field"),
                    "operator": rule.get("operator"),
                    "value": rule.get("value")
                }
            ] if rule.get("field") else None,
            "severity": rule.get("severity", "medium"),
            "active": True
        })

    # 3️⃣ Delete temp file
    os.remove(temp_path)
