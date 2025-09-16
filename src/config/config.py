"""Configuration management for FM Station Planner"""

import os
from typing import Dict, Optional
from dotenv import load_dotenv
from dataclasses import dataclass

load_dotenv()

@dataclass
class ModelConfig:
    """OpenRouter model configuration"""
    name: str
    max_tokens: int
    temperature: float
    cost_per_1k_input: float
    cost_per_1k_output: float
    use_case: str

class Config:
    """Application configuration"""

    # OpenRouter Configuration
    OPENROUTER_API_KEY = os.getenv("GERMINI_FLASH")
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

    # Supabase Configuration
    SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

    # Model Selection Strategy - Using Gemini Flash for all tasks
    MODELS = {
        "complex_reasoning": ModelConfig(
            name="google/gemini-flash-1.5",
            max_tokens=4096,
            temperature=0.3,
            cost_per_1k_input=0.000075,
            cost_per_1k_output=0.0003,
            use_case="Complex route planning and optimization"
        ),
        "thai_language": ModelConfig(
            name="google/gemini-flash-1.5",
            max_tokens=2048,
            temperature=0.5,
            cost_per_1k_input=0.000075,
            cost_per_1k_output=0.0003,
            use_case="Thai language processing and response generation"
        ),
        "simple_tasks": ModelConfig(
            name="google/gemini-flash-1.5",
            max_tokens=1024,
            temperature=0.3,
            cost_per_1k_input=0.000075,
            cost_per_1k_output=0.0003,
            use_case="Simple parsing and data extraction"
        ),
        "location_parsing": ModelConfig(
            name="google/gemini-flash-1.5",
            max_tokens=512,
            temperature=0.2,
            cost_per_1k_input=0.000075,
            cost_per_1k_output=0.0003,
            use_case="Location name parsing and geocoding"
        )
    }

    # Application Settings
    DEFAULT_INSPECTION_TIME_MINUTES = 10
    MAX_RESPONSE_TIME_SECONDS = 10
    CACHE_TTL_SECONDS = 3600
    MAX_RETRIES = 3

    # Geospatial Settings
    DEFAULT_SPEED_KMH = 40  # Average driving speed in urban areas

    @classmethod
    def get_model(cls, task_type: str) -> ModelConfig:
        """Get appropriate model configuration for task type"""
        return cls.MODELS.get(task_type, cls.MODELS["simple_tasks"])