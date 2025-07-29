from fastapi import FastAPI, UploadFile, Form, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI()

# Enable frontend access (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/upload")
async def upload_resume(
    resume: UploadFile = File(...),
    github_username: str = Form(...)
):
    contents = await resume.read()
    
    # Sample debug output
    print(f"Received resume: {resume.filename}")
    print(f"GitHub username: {github_username}")
    
    return JSONResponse({
        "message": "Uploaded successfully!",
        "filename": resume.filename,
        "github": github_username
    })

# Run server
if __name__ == "_main_":
    uvicorn.run(app, host="127.0.0.1", port=8000)

    from fastapi import FastAPI
    from backend import upload
    app = FastAPI()
    app.include_router(upload.router)