from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql://postgres:postgres@localhost:5432/job_rag"
    async_database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/job_rag"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    rag_model: str = "gpt-4o-mini"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    data_dir: str = "data/postings"
    profile_path: str = "data/profile.json"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    agent_model: str = "gpt-4o-mini"
    api_key: str = Field(default="", validation_alias="JOB_RAG_API_KEY")


settings = Settings()
