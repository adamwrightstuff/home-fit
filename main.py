from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

app = FastAPI(
    title="HomeFit API",
    description="Purpose-driven livability scoring API with 8 pillars",
    version="3.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    """Health check endpoint."""
    return {
        "service": "HomeFit API",
        "status": "running",
        "version": "3.0.0",
        "message": "Minimal version for testing"
    }

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "message": "Minimal app working"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
