"""
FastAPI Resume Upload Service - Production Ready Version
Secure file upload service with GitHub username validation
"""


from typing import Dict, List, Set, Tuple, Optional, Any
from fastapi import FastAPI, UploadFile, Form, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import os
import uuid
import re
import logging
from pathlib import Path
from datetime import datetime


# Optional: python-magic for MIME type validation (fallback gracefully if not available)
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
    logging.warning("python-magic not available. MIME type validation will be skipped.")


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('upload_service.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# Application configuration
app = FastAPI(
    title="Resume Upload Service",
    version="2.0.0",
    description="Secure resume upload service with GitHub username validation",
    docs_url="/docs",
    redoc_url="/redoc"
)


# CORS middleware - Production ready
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
        "https://yourdomain.com"  # Add your production domain
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Configuration constants
UPLOAD_DIR: str = "uploads"
ALLOWED_EXTENSIONS: Set[str] = {'.pdf', '.doc', '.docx', '.txt'}
MAX_FILE_SIZE: int = 5 * 1024 * 1024  # 5MB
MAX_FILENAME_LENGTH: int = 255
MAX_USERNAME_LENGTH: int = 39


# Valid MIME types for security (when python-magic is available)
VALID_MIME_TYPES: Dict[str, str] = {
    '.pdf': 'application/pdf',
    '.doc': 'application/msword',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.txt': 'text/plain'
}


# Create upload directory
os.makedirs(UPLOAD_DIR, exist_ok=True)


def validate_github_username(username: str) -> bool:
    """
    Validate GitHub username format according to GitHub rules.
    
    Args:
        username: The username to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not username or len(username) > MAX_USERNAME_LENGTH:
        return False
    
    # Single character must be alphanumeric
    if len(username) == 1:
        return username.isalnum()
    
    # Multi-character validation
    if username.startswith('-') or username.endswith('-') or '--' in username:
        return False
    
    # Only alphanumeric and hyphens allowed
    pattern = r'^[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]$'
    return bool(re.match(pattern, username))


def sanitize_filename(filename: str | None) -> str:
    """
    Sanitize filename to prevent security issues.
    
    Args:
        filename: Original filename (can be None)
        
    Returns:
        str: Sanitized filename
    """
    if not filename:
        return "unknown_file"
    
    # Remove or replace problematic characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove any path separators
    filename = os.path.basename(filename)
    
    # Limit length
    name, ext = os.path.splitext(filename)
    if len(name) > 100:
        name = name[:100]
    
    return f"{name}{ext}" if ext else name


def validate_file_content(filename: str) -> bool:
    """
    Validate file content matches extension using python-magic if available.
    
    Args:
        filename: Filename to validate (must exist in UPLOAD_DIR)
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not MAGIC_AVAILABLE:
        return True
    
    try:
        # Read file for content validation
        file_path = os.path.join(UPLOAD_DIR, filename)
        if not os.path.exists(file_path):
            return False
            
        with open(file_path, 'rb') as f:
            contents = f.read()
        
        # Detect actual file type
        mime = magic.from_buffer(contents, mime=True)
        file_ext = Path(filename).suffix.lower()
        
        # Check if extension matches content
        expected_mime = VALID_MIME_TYPES.get(file_ext)
        if expected_mime and mime != expected_mime:
            logger.warning(f"File content doesn't match extension. Expected {expected_mime}, got {mime}")
            return False
        
        return True
    except Exception as e:
        logger.warning(f"Could not validate file content: {e}")
        return True


def validate_path_security(filename: str) -> bool:
    """
    Prevent path traversal attacks.
    
    Args:
        filename: Filename to validate
        
    Returns:
        bool: True if safe, False if dangerous
    """
    if not filename:
        return False
    
    # Check for path traversal attempts
    dangerous_patterns = ['..', '/', '\\', '~']
    return not any(pattern in filename for pattern in dangerous_patterns)


def validate_file(file: UploadFile) -> Tuple[bool, str]:
    """
    Validate uploaded file properties.
    
    Args:
        file: The uploaded file object
        
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    if not file.filename:
        return False, "No filename provided"
    
    # Security check for path traversal
    if not validate_path_security(file.filename):
        return False, "Invalid filename: contains dangerous characters"
    
    # Check file extension
    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        return False, f"File type not allowed. Supported types: {', '.join(ALLOWED_EXTENSIONS)}"
    
    # Check filename length
    if len(file.filename) > MAX_FILENAME_LENGTH:
        return False, f"Filename too long (max {MAX_FILENAME_LENGTH} characters)"
    
    return True, "Valid"


@app.get("/", response_model=Dict[str, Any])
async def root() -> Dict[str, Any]:
    """Health check endpoint."""
    return {
        "message": "Resume Upload Service is running",
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "magic_available": MAGIC_AVAILABLE
    }


@app.post("/upload")
async def upload_resume(
    resume: UploadFile = File(..., description="Resume file (PDF, DOC, DOCX, TXT only)"),
    github_username: str = Form(..., description="GitHub username")
) -> JSONResponse:
    """
    Upload a resume file with associated GitHub username.
    
    Args:
        resume: The uploaded resume file
        github_username: Associated GitHub username
        
    Returns:
        JSONResponse containing upload information
        
    Raises:
        HTTPException: For various validation failures
    """
    try:
        # Validate GitHub username
        if not validate_github_username(github_username):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid GitHub username format. Must be 1-39 characters, "
                    "alphanumeric and hyphens only, cannot start/end with hyphen."
                )
            )
        
        # Validate file basic properties
        is_valid, error_message = validate_file(resume)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_message)
        
        # Check file size before reading (if available)
        if hasattr(resume, 'size') and resume.size:
            if resume.size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
                )
        
        # Read file contents
        contents = await resume.read()
        
        # Double-check size after reading
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        # Sanitize and generate unique filename
        sanitized_original = sanitize_filename(resume.filename)
        file_extension = Path(sanitized_original).suffix.lower()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{github_username}_{timestamp}_{uuid.uuid4().hex[:8]}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        # Save file atomically (prevents corruption)
        temp_path = f"{file_path}.tmp"
        try:
            # Write to temporary file first
            with open(temp_path, "wb") as f:
                f.write(contents)
            
            # Atomically move to final location
            os.rename(temp_path, file_path)
            
        except Exception as save_error:
            # Cleanup temp file if it exists
            if os.path.exists(temp_path):
                os.remove(temp_path)
            logger.error(f"Failed to save file: {save_error}")
            raise HTTPException(status_code=500, detail="Failed to save file")
        
        # Validate file content after saving
        if not validate_file_content(unique_filename):
            # Remove the saved file if validation fails
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(status_code=400, detail="File content validation failed")
        
        # Success response
        response_data = {
            "message": "Resume uploaded successfully!",
            "original_filename": resume.filename,
            "saved_filename": unique_filename,
            "github_username": github_username,
            "file_size": len(contents),
            "file_size_human": f"{len(contents) / (1024*1024):.2f} MB",
            "file_type": file_extension,
            "upload_timestamp": timestamp,
            "upload_id": uuid.uuid4().hex[:16]
        }
        
        logger.info(
            f"✅ Uploaded: {resume.filename} -> {unique_filename} for user: {github_username}"
        )
        
        return JSONResponse(response_data, status_code=200)
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"❌ Upload error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred"
        )


@app.get("/uploads", response_model=Dict[str, Any])
async def list_uploads() -> Dict[str, Any]:
    """List all uploaded files with metadata."""
    try:
        files = []
        for filename in os.listdir(UPLOAD_DIR):
            file_path = os.path.join(UPLOAD_DIR, filename)
            if os.path.isfile(file_path):
                file_stats = os.stat(file_path)
                
                # Extract GitHub username from filename
                username = filename.split('_')[0] if '_' in filename else "unknown"
                
                files.append({
                    "filename": filename,
                    "github_username": username,
                    "size": file_stats.st_size,
                    "size_human": f"{file_stats.st_size / (1024*1024):.2f} MB",
                    "created": datetime.fromtimestamp(file_stats.st_ctime).isoformat(),
                    "modified": datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
                    "extension": Path(filename).suffix.lower()
                })
        
        return {
            "total_files": len(files),
            "files": sorted(files, key=lambda x: x["created"], reverse=True)
        }
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail="Error listing files")


@app.get("/uploads/{filename}", response_model=Dict[str, Any])
async def get_upload_info(filename: str) -> Dict[str, Any]:
    """Get detailed information about a specific uploaded file."""
    
    # Security: Prevent path traversal attacks
    if not validate_path_security(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    # Ensure filename doesn't contain directory separators
    clean_filename = os.path.basename(filename)
    file_path = os.path.join(UPLOAD_DIR, clean_filename)
    
    # Additional security check: ensure path is within upload directory
    if not os.path.abspath(file_path).startswith(os.path.abspath(UPLOAD_DIR)):
        raise HTTPException(status_code=400, detail="Invalid file path")
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        file_stats = os.stat(file_path)
        
        # Extract GitHub username from filename
        username = clean_filename.split('_')[0] if '_' in clean_filename else "unknown"
        
        return {
            "filename": clean_filename,
            "github_username": username,
            "size": file_stats.st_size,
            "size_human": f"{file_stats.st_size / (1024*1024):.2f} MB",
            "created": datetime.fromtimestamp(file_stats.st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
            "extension": Path(clean_filename).suffix.lower(),
            "absolute_path": os.path.abspath(file_path)
        }
    except Exception as e:
        logger.error(f"Error getting file info for {filename}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving file information")


@app.delete("/uploads/{filename}", response_model=Dict[str, Any])
async def delete_upload(filename: str) -> Dict[str, Any]:
    """Delete a specific uploaded file."""
    
    # Security: Prevent path traversal attacks
    if not validate_path_security(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    # Ensure filename doesn't contain directory separators
    clean_filename = os.path.basename(filename)
    file_path = os.path.join(UPLOAD_DIR, clean_filename)
    
    # Additional security check
    if not os.path.abspath(file_path).startswith(os.path.abspath(UPLOAD_DIR)):
        raise HTTPException(status_code=400, detail="Invalid file path")
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        # Get file info before deletion
        file_stats = os.stat(file_path)
        file_size = file_stats.st_size
        
        # Delete the file
        os.remove(file_path)
        
        logger.info(f"✅ Deleted file: {clean_filename} (Size: {file_size} bytes)")
        
        return {
            "message": f"File {clean_filename} deleted successfully",
            "deleted_filename": clean_filename,
            "deleted_size": file_size,
            "deleted_at": datetime.now().isoformat()
        }
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied: cannot delete file")
    except Exception as e:
        logger.error(f"❌ Error deleting {clean_filename}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete file")


@app.get("/stats", response_model=Dict[str, Any])
async def get_upload_stats() -> Dict[str, Any]:
    """Get comprehensive upload statistics."""
    try:
        total_files = 0
        total_size = 0
        file_types: Dict[str, int] = {}
        users: Set[str] = set()
        
        for filename in os.listdir(UPLOAD_DIR):
            file_path = os.path.join(UPLOAD_DIR, filename)
            if os.path.isfile(file_path):
                total_files += 1
                
                # Get file size
                file_size = os.path.getsize(file_path)
                total_size += file_size
                
                # Count file types
                ext = Path(filename).suffix.lower()
                file_types[ext] = file_types.get(ext, 0) + 1
                
                # Extract usernames
                username = filename.split('_')[0] if '_' in filename else "unknown"
                users.add(username)
        
        average_size = (total_size / total_files) if total_files > 0 else 0
        
        return {
            "total_files": total_files,
            "total_size": total_size,
            "total_size_human": f"{total_size / (1024*1024):.2f} MB",
            "unique_users": len(users),
            "file_types": file_types,
            "average_file_size": f"{average_size / (1024*1024):.2f} MB"
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving statistics")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )
