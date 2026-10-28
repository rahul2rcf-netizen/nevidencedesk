from functools import lru_cache
import os
from dataclasses import dataclass, fields
from pathlib import Path


@dataclass
class Settings:
    data_dir: Path = Path("./data")
    max_upload_mb: int = 25
    chunk_size: int = 900
    chunk_overlap: int = 120
    retrieval_mode: str = "hybrid"
    vector_weight: float = 0.55
    bm25_weight: float = 0.45
    embedding_provider: str = "local"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    llm_provider: str = "extractive"
    llm_model: str = ""
    llm_base_url: str = ""
    llm_api_key: str = ""
    min_relevance: float = 0.40
    outdated_after_days: int = 365

    def __post_init__(self):
        for item in fields(self):
            env_value = os.getenv(f"ED_{item.name.upper()}")
            if env_value is not None and getattr(self, item.name) == item.default:
                default = item.default
                converted = Path(env_value) if isinstance(default, Path) else type(default)(env_value)
                setattr(self, item.name, converted)
        if not 1 <= self.max_upload_mb <= 250:
            raise ValueError("ED_MAX_UPLOAD_MB must be from 1 to 250")
        if not 200 <= self.chunk_size <= 4000:
            raise ValueError("ED_CHUNK_SIZE must be from 200 to 4000")
        if not 0 <= self.chunk_overlap < self.chunk_size:
            raise ValueError("ED_CHUNK_OVERLAP must be non-negative and smaller than chunk size")
        if self.retrieval_mode not in {"hybrid", "vector", "bm25"}:
            raise ValueError("ED_RETRIEVAL_MODE must be hybrid, vector, or bm25")
        if self.embedding_provider not in {"local", "hash"}:
            raise ValueError("ED_EMBEDDING_PROVIDER must be local or hash")
        if self.llm_provider not in {"extractive", "openai-compatible"}:
            raise ValueError("ED_LLM_PROVIDER must be extractive or openai-compatible")
        if self.llm_provider == "openai-compatible" and not self.llm_base_url and not self.llm_api_key:
            raise ValueError("Set ED_LLM_API_KEY for a hosted OpenAI-compatible endpoint")
        if self.llm_provider == "openai-compatible" and not self.llm_model:
            raise ValueError("ED_LLM_MODEL is required when ED_LLM_PROVIDER=openai-compatible")
        if not 0 <= self.vector_weight <= 1 or not 0 <= self.bm25_weight <= 1:
            raise ValueError("Retrieval weights must be in [0, 1]")
        if not 0 <= self.min_relevance <= 1:
            raise ValueError("ED_MIN_RELEVANCE must be in [0, 1]")
        if not 30 <= self.outdated_after_days <= 3650:
            raise ValueError("ED_OUTDATED_AFTER_DAYS must be from 30 to 3650")


@lru_cache
def get_settings() -> Settings:
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() and not key.strip().startswith("#"):
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
    return Settings()
