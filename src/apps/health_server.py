# src/apps/health_server.py
from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
async def health():
    return await manager.health_check()


@app.get("/ready")
async def ready():
    return {"ready": manager.is_initialized()}
