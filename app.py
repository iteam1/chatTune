import logging
from dotenv import load_dotenv
load_dotenv()

from pathlib import Path
from typing import Any

from autogen_core import CancellationToken
from autogen_agentchat.messages import ChatMessage

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.utils import get_chat_agent, get_history

model_config_path = Path("model_config.yaml")
state_path = Path("chat_agent_state.json")
history_path = Path("chat_agent_history.json")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Serve static files
app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/")
async def root():
    """Serve the chat interface HTML file."""
    return FileResponse("app.html")


@app.get("/history")
async def history() -> list[dict[str, Any]]:
    try:
        return await get_history()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

# ws/chat

if __name__ == "__main__":

    import uvicorn
    
    uvicorn.run(app, host="0.0.0.0", port=8000)