from pathlib import Path
from typing import Literal
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    camera_source: Literal['webcam', 'whatsapp'] = 'webcam'
    camera_index: int = Field(default=0, ge=0, le=20)
    camera_width: int = Field(default=1280, ge=320, le=4096)
    camera_height: int = Field(default=720, ge=240, le=2160)
    frontend_origin: str = 'http://localhost:3000'
    data_dir: Path = Path(__file__).resolve().parents[1] / 'data' / 'tasks'
    gemini_api_key: SecretStr = SecretStr('')
    gemini_model: str = ''
    gemini_timeout_seconds: int = Field(default=120, ge=5, le=120)
    gemini_thinking_level: Literal['low', 'medium', 'high'] | None = None
