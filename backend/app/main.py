"""FastAPI application entry point."""

from fastapi import FastAPI

app = FastAPI(title="Silsila Backend API", version="0.1.0")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
