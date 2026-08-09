from datetime import UTC, datetime

from fastapi import FastAPI

from app.routers import items

app = FastAPI(title="Test FastAPI", version="0.1.1")
app.include_router(items.router)

@app.get("/")
def root():
  return {
    "message": "Test FastAPI is running...",
      "time": datetime.now(UTC).isoformat()
  }
  
@app.get("/health")
def health():
  return {
    "status": "ok",
    "time": datetime.now(UTC).isoformat()
  }