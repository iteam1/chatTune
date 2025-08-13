import os
from dotenv import load_dotenv
load_dotenv()

import json
import asyncio
from autogen_agentchat.ui import Console
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from models import MusicSearchQuery
from tools import search_music_by_mood

mood_detector = AssistantAgent(
    name="mood_detector",
    model_client=OpenAIChatCompletionClient(
        model="gpt-4o-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
    ),
    system_message=f"""
    You are a mood detector.
    Your job is to detect the mood of the user 
    base on user's message or conversation history.
    And return the query structure following the given json schema.
    {json.dumps(MusicSearchQuery.model_json_schema(), indent=2)}
    ONLY RETURN THE QUERY STRUCTURE. DO NOT RETURN ANYTHING ELSE.
    """
)

music_retriever = AssistantAgent(
    name="music_retriever",
    model_client=OpenAIChatCompletionClient(
        model="gpt-4o-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
    ),
    system_message=f"""
    You are a music retriever.
    Your job is to retrieve music based on the JSON query structure provided by the mood_detector.
    
    When you receive a JSON query structure, extract the individual fields and call the search_music_by_mood function.
    
    For example, if you receive:
    {{
      "mood": "Happy",
      "energy_level": 75,
      "happiness_level": 80,
      "genres": ["Pop", "Electronic"]
    }}
    
    Call the function like this:
    search_music_by_mood(mood="Happy", energy_level=75, happiness_level=80, genres=["Pop", "Electronic"])
    
    Always pass all available fields from the JSON, even if they are null.
    """,
    tools=[search_music_by_mood]
)

approver = AssistantAgent(
    name="approver",
    model_client=OpenAIChatCompletionClient(
        model="gpt-4o-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
    ),
    system_message="""
    You are an approver.
    Your job is to approve the music retrieved by the music_retriever.
    When you receive a list of songs, approve them by saying "APPROVED".
    """
)

termination_condition = MaxMessageTermination(10) | TextMentionTermination("APPROVED")
team = RoundRobinGroupChat([mood_detector, music_retriever, approver],
                    termination_condition=termination_condition)

if __name__ == "__main__":

    asyncio.run(Console(team.run_stream(task="I feel sad.")))