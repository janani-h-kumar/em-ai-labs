from fastapi import FastAPI
from src.application_service import ApplicationService

app = FastAPI()
manager = ApplicationService()


@app.get("/health")
async def health():
    return await manager.health_check()
