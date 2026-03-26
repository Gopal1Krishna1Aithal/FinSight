import os
import json
from io import BytesIO
import re
from PIL import Image
from pillow_heif import register_heif_opener
from google import genai
from google.genai import types

# Register HEIC opener for Pillow
register_heif_opener()

# System prompt for Vision models to act purely as an OCR table extractor
VISION_SYSTEM_PROMPT = """You are a highly precise data extraction engine. 
Your task is to extract bank transaction table rows from the provided statement image.
Return ONLY valid JSON in this exact structure, with nothing else:
[
  {
    "Date": "DD/MM/YY",
    "Narration": "Transaction description",
    "Ref_No": "Reference number or empty string",
    "Value_Date": "DD/MM/YY or empty string",
    "Debit": "Amount as string without commas, or empty string",
    "Credit": "Amount as string without commas, or empty string",
    "Balance": "Amount as string without commas, or empty string"
  }
]

IMPORTANT RULES:
- Ignore page headers, summary blocks, and footers. Extract ONLY the transaction rows.
- If a narration spans multiple lines in the image, combine them into a single string with spaces.
- If a column is blank in the image, leave it as an empty string "".
- Do not make up information. 
- Return the full list of parsed transactions.
- Remove thousand separator commas from numerical amounts (e.g., "1,234.56" -> "1234.56").
- The Date column must exactly match the DD/MM/YY format visible in the sheet.
"""

class ImageOCRExtractor:
    """
    Extracts transaction data from a sequential list of image files (JPG/PNG/HEIC)
    using the Google Gemini Vision API. Mimics the exact list[dict] output of HDFCPDFExtractor.
    """
    
    def __init__(self, image_paths: list[str], api_key: str = None):
        self.image_paths = sorted(image_paths)
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY must be configured for Gemini Vision extraction (Add to .env file).")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = "gemini-2.5-flash"

    def extract(self) -> list[dict]:
        all_rows = []
        for i, img_path in enumerate(self.image_paths, 1):
            print(f"      [OCR] Processing page {i}/{len(self.image_paths)}: {os.path.basename(img_path)}...")
            
            try:
                # Prepare image for Gemini. The PIL Image format is directly supported by the python SDK.
                pil_image = self._prepare_image(img_path)
                
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=["Extract the transactions exactly as requested in JSON format.", pil_image],
                    config=types.GenerateContentConfig(
                        system_instruction=VISION_SYSTEM_PROMPT,
                        temperature=0.0
                    )
                )
                
                raw_text = response.text.strip()
                
                # Strip backticks if the model enclosed it in markdown
                json_match = re.search(r'\[.*\]', raw_text, re.DOTALL)
                
                if json_match:
                    page_rows = json.loads(json_match.group(0))
                    if isinstance(page_rows, list):
                        all_rows.extend(page_rows)
                    else:
                        print(f"      [OCR] Warning: Expected list of dicts, got {type(page_rows)} on {img_path}")
                else:
                    print(f"      [OCR] Warning: No JSON array detected on {img_path}. Model output: {raw_text[:100]}...")
                    
            except Exception as e:
                print(f"      [OCR] Error extracting {img_path}: {e}")
                
        return all_rows

    def _prepare_image(self, image_path: str) -> Image.Image:
        """
        Reads an image (including HEIC), converts it to standard RGB, 
        downscales it if it's too massive, and returns a PIL Image for Gemini.
        """
        MAX_DIMENSION = 2000
        
        img = Image.open(image_path)
        if img.mode != "RGB":
            img = img.convert("RGB")
        
        width, height = img.size
        if max(width, height) > MAX_DIMENSION:
            scale_factor = MAX_DIMENSION / max(width, height)
            new_size = (int(width * scale_factor), int(height * scale_factor))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        return img
