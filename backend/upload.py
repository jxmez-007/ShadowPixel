from fastapi import APIRouter, UploadFile, Form
from fastapi.responses import JSONResponse
import fitz 
import os

router = APIRouter()

UPLOAD_DIR = "uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def extract_pdf_text(file_path):
    text = ""
    with fitz.open(file_path) as doc:
        for page in doc:
            text += page.get_text()
    return text

@router.post("/upload/")
async def upload_resume(resume: UploadFile, github: str = Form(...)):
    file_location = f"{UPLOAD_DIR}/{resume.filename}"
    with open(file_location, "wb") as f:
        f.write(await resume.read())

    text = extract_pdf_text(file_location)
    summary = text[:300] 

    return JSONResponse({
        "message": "Uploaded successfully!",
        "github": github,
        "summary": summary
    })