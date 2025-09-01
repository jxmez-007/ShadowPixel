from fastapi import FastAPI, UploadFile, Form, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import os
import uuid
import re
from pathlib import Path

app = FastAPI(title="Resume Upload Service", version="1.0.0")

# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
UPLOAD_DIR = "uploads"
ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.txt'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

# Create upload directory
os.makedirs(UPLOAD_DIR, exist_ok=True)

def validate_github_username(username: str) -> bool:
    """Validate GitHub username format"""
    # GitHub usernames can contain alphanumeric characters and hyphens
    # Cannot start or end with hyphen, cannot have consecutive hyphens
    pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-])*[a-zA-Z0-9]$|^[a-zA-Z0-9]$'
    return bool(re.match(pattern, username)) and len(username) <= 39

def validate_file(file: UploadFile) -> tuple[bool, str]:
    """Validate uploaded file"""
    if not file.filename:
        return False, "No filename provided"
    
    # Check file extension
    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        return False, f"File type not allowed. Supported types: {', '.join(ALLOWED_EXTENSIONS)}"
    
    return True, "Valid"

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Resume Upload Service is running", "status": "healthy"}

@app.post("/upload")
async def upload_resume(
    resume: UploadFile = File(..., description="Resume file (PDF, DOC, DOCX, TXT only)"),
    github_username: str = Form(..., description="GitHub username")
):
    """
    Upload a resume file with associated GitHub username
    """
    try:
        # Validate GitHub username
        if not validate_github_username(github_username):
            raise HTTPException(
                status_code=400,
                detail="Invalid GitHub username format. Must be 1-39 characters, alphanumeric and hyphens only."
            )
        
        # Validate file
        is_valid, error_message = validate_file(resume)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_message)
        
        # Read file contents
        contents = await resume.read()
        
        # Check file size
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size allowed: {MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        # Generate unique filename to prevent conflicts
        file_extension = Path(resume.filename).suffix.lower()
        unique_filename = f"{github_username}_{uuid.uuid4().hex[:8]}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        # Save file to disk
        with open(file_path, "wb") as f:
            f.write(contents)
        
        # Success response
        response_data = {
            "message": "Resume uploaded successfully!",
            "original_filename": resume.filename,
            "saved_filename": unique_filename,
            "github_username": github_username,
            "file_size": len(contents),
            "file_type": file_extension
        }
        
        # Debug prints
        print(f"✅ Uploaded: {resume.filename} -> {unique_filename}")
        print(f"✅ GitHub: {github_username}")
        print(f"✅ Size: {len(contents)} bytes")
        
        return JSONResponse(response_data, status_code=200)
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle unexpected errors
        print(f"❌ Upload error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@app.get("/uploads/{filename}")
async def get_upload_info(filename: str):
    """Get information about an uploaded file"""
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    file_stats = os.stat(file_path)
    return {
        "filename": filename,
        "size": file_stats.st_size,
        "created": file_stats.st_ctime,
        "modified": file_stats.st_mtime
    }

@app.delete("/uploads/{filename}")
async def delete_upload(filename: str):
    """Delete an uploaded file"""
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        os.remove(file_path)
        return {"message": f"File {filename} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")

# Run app
if __name__ == "__main__":
    # Change "main" to your filename (without .py)
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)