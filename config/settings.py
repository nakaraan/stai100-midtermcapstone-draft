# Centralized application settings for AGENT P, from .env
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- NREL / NSRDB API ---
    # Sign up for a free key at https://developer.nlr.gov/signup/
    # NOTE: developer.nrel.gov was retired; developer.nlr.gov is the current
    # domain (same registrant per the official CISA .gov registry — Dept. of
    # Energy / NREL, Golden CO — and fronted by cloud.gov/api.data.gov, verified
    # 2026-07-08). Confirm current domain periodically since this program has a
    # history of domain confusion — don't restore the old nrel.gov value blind.
    nrel_api_key: str = Field(..., alias="NREL_API_KEY")
    nrel_api_email: str = Field(..., alias="NREL_API_EMAIL")

    # NSRDB is split into region-specific datasets. Target sites in the Philippines
    # (e.g. the Caloocan warehouse sample query) fall under the Himawari (Asia/Pacific)
    # coverage area, so that is the default download endpoint.
    nrel_nsrdb_base_url: str = Field(
        default="https://developer.nlr.gov/api/nsrdb/v2/solar/himawari-download.json",
        alias="NREL_NSRDB_BASE_URL",
    )
    nrel_request_timeout_seconds: int = Field(default=60, alias="NREL_REQUEST_TIMEOUT_SECONDS")

    # MLflow (LLMOps monitoring)
    mlflow_tracking_uri: str = Field(default="http://localhost:5000", alias="MLFLOW_TRACKING_URI")
    mlflow_registry_uri: str | None = Field(default=None, alias="MLFLOW_REGISTRY_URI")
    mlflow_experiment_name: str = Field(default="agent-p-solar-analytics", alias="MLFLOW_EXPERIMENT_NAME")

    # LLM (intent parsing, disambiguation, response generation in src/agent.py)
    # Defaults point at a local Ollama server via its OpenAI-compatible endpoint.
    llm_base_url: str = Field(default="http://localhost:11434/v1", alias="LLM_BASE_URL")
    llm_api_key: str = Field(default="ollama", alias="LLM_API_KEY")
    llm_model: str = Field(default="llama3.2:3b", alias="LLM_MODEL")


@lru_cache
def get_settings() -> Settings:
    return Settings()
