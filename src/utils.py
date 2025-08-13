import yaml
import aiofiles
import json
from pathlib import Path
from typing import Any
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.agents import AssistantAgent

# Get chat agent
async def get_chat_agent(model_config_path: Path,
                         state_path: Path)-> AssistantAgent:
    """
    Get chat agent
    Args:
    - model_config_path: Path to model config yaml file
    - state_path: Path to state json file
    Returns:
    - chat_agent: AssistantAgent
    """
    # Load model config
    async with aiofiles.open(model_config_path, 'r') as f:
        content = await f.read()
        model_config = yaml.safe_load(content)

    model_client = OpenAIChatCompletionClient.load_component(model_config)
   
    # Create chat agent
    chat_agent = AssistantAgent(
        name="chat_agent",
        model_client=model_client,
        system_message="""
        You are helpful assistant.
        """
    )

    # Load state if exists
    if not state_path.exists():
        return chat_agent
    
    async with aiofiles.open(state_path, "r") as file:
        text = await file.read()
    state: dict[str, Any] = {}
    if text.strip():
        try:
            state = json.loads(text)
        except Exception:
            state = {}
    await chat_agent.load_state(state)
    return chat_agent
    
# Get chat history
async def get_history(history_path: Path) -> list[dict[str, Any]]:
    """Get chat history from file.
    Args:
    - history_path: Path to history json file
    Returns:
    - history: list of chat messages
    """
    if not history_path.exists():
        return []
    async with aiofiles.open(history_path, "r") as file:
        text = await file.read()
    if not text.strip():
        return []
    try:
        return json.loads(text)
    except Exception:
        return []