from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, validator

class MoodEnum(str, Enum):
    HAPPY = "Happy"
    SAD = "Sad"
    ENERGETIC = "Energetic"
    RELAXED = "Relaxed"
    FOCUSED = "Focused"

class GenreEnum(str, Enum):
    POP = "Pop"
    COUNTRY = "Country"
    RNB = "R&B"
    ACOUSTIC = "Acoustic"
    ROCK = "Rock"
    CLASSIC_ROCK = "Classic Rock"
    JAZZ = "Jazz"
    CLASSICAL = "Classical"
    HIP_HOP = "Hip Hop"
    RAP = "Rap"
    ELECTRONIC = "Electronic"
    DANCE = "Dance"
    HARD_ROCK = "Hard Rock"
    GRUNGE = "Grunge"
    ALTERNATIVE = "Alternative"
    DANCEHALL = "Dancehall"
    AFROBEAT = "Afrobeat"
    # Add other genres as needed

class MusicSearchQuery(BaseModel):
    # Predefined mood selection (one of the mood buttons)
    mood: Optional[MoodEnum] = None
    
    # Custom mood sliders
    energy_level: Optional[int] = Field(
        None, 
        ge=0, 
        le=100, 
        description="Energy level from 0 (Calm) to 100 (Energetic)"
    )
    happiness_level: Optional[int] = Field(
        None, 
        ge=0, 
        le=100, 
        description="Happiness level from 0 (Melancholic) to 100 (Joyful)"
    )
    
    # Genre selections
    genres: Optional[List[GenreEnum]] = Field(
        None, 
        description="List of music genres to filter by"
    )
    
    @validator('energy_level', 'happiness_level')
    def validate_levels(cls, v):
        """Ensure slider values are within the valid range."""
        if v is not None and (v < 0 or v > 100):
            raise ValueError(f"Level must be between 0 and 100, got {v}")
        return v
    
    class Config:
        use_enum_values = True  # Use string values instead of enum objects
        schema_extra = {
            "example": {
                "mood": "Happy",
                "energy_level": 75,
                "happiness_level": 80,
                "genres": ["Pop", "Electronic"]
            }
        }