from fastapi import FastAPI

from src.agent_manager import AgentManager

app = FastAPI()
manager = AgentManager()

manager = AgentManager()


@app.get("/health")
async def health():
    return await manager.health_check()
