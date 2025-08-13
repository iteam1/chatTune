import yaml
import aiofiles
import json
from pathlib import Path
from typing import Any
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.agents import AssistantAgent
from src.teams import get_music_team
from src.models import MusicSearchQuery

# Format music team response
async def format_music_team_response(team_result) -> str:
    """
    Format the music team response for the chat interface
    Args:
    - team_result: Result from music team execution
    Returns:
    - formatted_response: Formatted string response
    """
    try:
        # Extract the last message from the team result
        if hasattr(team_result, 'messages') and team_result.messages:
            last_message = team_result.messages[-1]
            if hasattr(last_message, 'content'):
                return last_message.content
        
        # Fallback: convert to string
        return str(team_result)
    except Exception as e:
        return f"I found some music for you, but had trouble formatting the response. Error: {str(e)}"

# Search music for user
async def search_music_for_user(description: str) -> str:
    """
    Tool for the main chat agent to search music based on user's description.
    This function will be called by the chat agent when users ask for music.
    
    Args:
    - description: The user's description (e.g., "I want happy music", "Play some jazz")
    
    Returns:
    - raw_music_data: Raw music search results for the chat agent to format naturally
    """
    try:
        # Get music team and process the request
        music_team = await get_music_team()
        team_result = await music_team.run(task=description)
        
        # Get the raw music team response (don't format it here - let chat agent handle formatting)
        response = await format_music_team_response(team_result)
        
        # Return raw data with instruction for chat agent to format naturally
        return f"MUSIC_SEARCH_RESULTS: {response}"
        
    except Exception as e:
        return f"MUSIC_SEARCH_ERROR: I had trouble finding music for you. Error: {str(e)}"

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
        system_message=f"""
        You are a caring, empathetic assistant focused on the user’s emotional well-being.

        Your role:
            - Listen with compassion and understanding
            - Engage in meaningful conversations about thoughts, feelings, and experiences
            - Offer emotional support, encouragement, and thoughtful responses
            - Be a trusted companion who cares about their inner state

        Music search tool (use sparingly):
            - Suggest music only when the user asks, or when it may genuinely help
            - Consider their emotional state (sad, stressed, lonely, etc.)
            - Music should comfort, not distract from real problems

        When recommending music, gather naturally:
            - Mood - Ask/observe how they feel (happy, sad, relaxed, energetic, focused)
            - Energy - Calm vs. energizing preference
            - Happiness - Lifting spirits or processing feelings
            - Genres - Music styles they enjoy

        When calling search_music_for_user:
            - Pass a rich description including emotional state, situation, context, and music type that may help
            - Avoid short generic requests like "happy music"

        When you receive music search results:
        1. Pick 2-3 songs to highlight with personal, caring descriptions
        2. Explain WHY these songs might help based on the conversation
        3. Ask follow-up questions about their preferences
        4. Respond as a caring friend with natural language

        Goal:
        Prioritize emotional connection; music is just one supportive tool.
        """,
        tools=[search_music_for_user]
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