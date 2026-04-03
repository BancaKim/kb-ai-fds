from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"

    # Rule engine
    rule_engine_llm_threshold: int = 50  # 이 점수 이상이면 LLM 평가
    rule_engine_block_threshold: int = 80  # 이 점수 이상이면 자동 차단

    # RAG
    chroma_db_path: str = "./chroma_db"
    rag_top_k: int = 3

    # Database
    sqlite_db_path: str = "./fds.db"

    model_config = {"env_file": ".env"}


settings = Settings()
