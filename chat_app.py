import os
import logging
from dotenv import load_dotenv
load_dotenv()

import json
import aiofiles
import agentops

from pathlib import Path
from typing import Any

from autogen_core import CancellationToken
from autogen_agentchat.messages import TextMessage

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

from src.utils import get_chat_agent, get_history

# Initialize paths
model_config_path = Path("model_config.yaml")
state_path = Path("chat_agent_state.json")
history_path = Path("chat_agent_history.json")

# Initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize AgentOps
AGENTOPS_API_KEY = os.getenv("AGENTOPS_API_KEY") 
agentops.init(AGENTOPS_API_KEY) 

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
    return FileResponse("chat_ui.html")

@app.get("/history")
async def history() -> list[dict[str, Any]]:
    try:
        return await get_history(history_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

# WebSocket endpoint for chat
@app.websocket("/ws/chat")
async def chat(websocket: WebSocket):
    # Wait for connection
    await websocket.accept()
    
    try:
        while True:
            # Get user message from client
            data = await websocket.receive_json()
            # Create a TextMessage with the content from the client
            request = TextMessage(content=data.get('content', ''), source=data.get('source', 'user'))

            # Create agent
            chat_agent = await get_chat_agent(model_config_path,
                                                    state_path)

            # Generate response            
            response = await chat_agent.on_messages(messages=[request],
                                                    cancellation_token=CancellationToken())

            # Debug: Log the response structure
            logger.info(f"Response type: {type(response)}")
            logger.info(f"Response attributes: {dir(response)}")
            
            # Save agent state to file.
            state = await chat_agent.save_state()
            async with aiofiles.open(state_path, "w") as file:
                await file.write(json.dumps(state, default=str))

            # Extract response content safely
            response_content = "I'm sorry, I couldn't generate a response."
            
            # Extract response content from response 
            try:
                response_content = response.chat_message.content
            except Exception as e:
                logger.error(f"Error extracting response content: {e}")

            # Save chat history to file.
            history = await get_history(history_path)
            # Add user message to history
            history.append({"content": request.content, "source": "user"})
            # Add assistant response to history
            history.append({"content": response_content, "source": "assistant"})

            async with aiofiles.open(history_path, "w") as file:
                await file.write(json.dumps(history, default=str))

            # Send response back to client
            response_data = {
                "content": response_content,
                "source": "assistant"
            }

            # Send response back to client
            await websocket.send_json(response_data)
            
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Error: {e}")
        try:
            await websocket.close()
        except:
            pass

if __name__ == "__main__":

    import uvicorn
    
    uvicorn.run(app, host="0.0.0.0", port=8000)