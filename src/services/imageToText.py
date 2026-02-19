import httpx
from dotenv import load_dotenv
import os
load_dotenv()
async def extract_image_to_text_online(file_path: str):
    url = "https://api.ocr.space/parse/image"
    api_key = os.getenv('IMAGE_OCR')  # Replace with your API key

    with open(file_path, "rb") as f:
        files = {"file": f}
        data = {
            "apikey": api_key,
            "language": "eng",
            "isOverlayRequired": False
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data, files=files)
    result = response.json()
    parsed_text = ""
    if result["ParsedResults"]:
        parsed_text = result["ParsedResults"][0]["ParsedText"]
    return parsed_text
