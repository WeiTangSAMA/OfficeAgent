from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_data_dir: Path = Path("data")
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_embedding_model: str = "text-embedding-v4"
    qwen_model: str = "qwen3.7-plus"
    qwen_temperature: float = 0.2
    qwen_timeout_seconds: int = 120
    qwen_max_retries: int = 2
    max_file_size_mb: int = 25
    max_workspace_size_mb: int = 100
    max_files_per_upload: int = 20
    max_task_runtime_seconds: int = 300

settings = Settings()
settings.app_data_dir = settings.app_data_dir.resolve()
settings.app_data_dir.mkdir(parents=True, exist_ok=True)
