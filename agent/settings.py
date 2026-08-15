import os
from dataclasses import dataclass

DEFAULT_OPENAI_COMPATIBLE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_LOCAL_MODELS_ROOT = "./models"
DEFAULT_LOCAL_EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
DEFAULT_LOCAL_EMBEDDING_FALLBACK_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_RAG_CHUNK_SIZE = 500
DEFAULT_RAG_CHUNK_OVERLAP = 80
DEFAULT_RAG_DENSE_CANDIDATE_K = 30
DEFAULT_RAG_SPARSE_CANDIDATE_K = 30
DEFAULT_RAG_RRF_CANDIDATE_K = 40
DEFAULT_RAG_RERANK_CANDIDATE_K = 50
DEFAULT_RAG_TOP_K = 8
DEFAULT_RAG_RERANK_ENABLED = True
DEFAULT_RAG_PROJECT_MAX_CHARS = 0
DEFAULT_RAG_PROJECT_MAX_CHUNKS = 0
DEFAULT_RAG_PROJECT_RERANK_ENABLED = True
DEFAULT_RAG_RERANK_MODEL = "ms-marco-MiniLM-L-12-v2"
DEFAULT_RAG_HYBRID_ENABLED = True
DEFAULT_RAG_NEIGHBOR_EXPANSION = True
DEFAULT_RAG_NEIGHBOR_COUNT = 1
DEFAULT_RAG_QUERY_PREPROCESS_ENABLED = False
DEFAULT_AGENT_TEMPERATURE = 0.1
DEFAULT_AGENT_ENABLE_THINKING = False
DEFAULT_AGENT_REASONING_EFFORT = ""
DEFAULT_AGENT_LLM_REQUEST_TIMEOUT = 120.0


@dataclass(frozen=True)
class AgentSettings:
    openai_compatible_base_url: str
    local_embedding_model: str
    local_embedding_fallback_model: str
    local_models_root: str
    local_embedding_cache_dir: str
    local_rerank_cache_dir: str
    rag_chunk_size: int
    rag_chunk_overlap: int
    rag_dense_candidate_k: int
    rag_sparse_candidate_k: int
    rag_rrf_candidate_k: int
    rag_rerank_candidate_k: int
    rag_top_k: int
    rag_rerank_enabled: bool
    rag_project_max_chars: int
    rag_project_max_chunks: int
    rag_project_rerank_enabled: bool
    rag_rerank_model: str
    rag_hybrid_enabled: bool
    rag_neighbor_expansion: bool
    rag_neighbor_count: int
    rag_query_preprocess_enabled: bool
    agent_temperature: float
    agent_enable_thinking: bool
    agent_reasoning_effort: str
    agent_llm_request_timeout: float


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def load_agent_settings() -> AgentSettings:
    models_root = os.getenv("LOCAL_MODELS_ROOT", DEFAULT_LOCAL_MODELS_ROOT)
    return AgentSettings(
        openai_compatible_base_url=os.getenv(
            "OPENAI_COMPATIBLE_BASE_URL", DEFAULT_OPENAI_COMPATIBLE_BASE_URL
        ),
        local_embedding_model=os.getenv("LOCAL_RAG_EMBEDDING_MODEL", DEFAULT_LOCAL_EMBEDDING_MODEL),
        local_embedding_fallback_model=os.getenv(
            "LOCAL_RAG_EMBEDDING_FALLBACK_MODEL",
            DEFAULT_LOCAL_EMBEDDING_FALLBACK_MODEL,
        ),
        local_models_root=models_root,
        local_embedding_cache_dir=os.getenv(
            "LOCAL_RAG_EMBEDDING_CACHE_DIR", f"{models_root}/embeddings"
        ),
        local_rerank_cache_dir=os.getenv(
            "LOCAL_RAG_RERANK_CACHE_DIR", f"{models_root}/flashrank"
        ),
        rag_chunk_size=_env_int("LOCAL_RAG_CHUNK_SIZE", DEFAULT_RAG_CHUNK_SIZE),
        rag_chunk_overlap=_env_int("LOCAL_RAG_CHUNK_OVERLAP", DEFAULT_RAG_CHUNK_OVERLAP),
        rag_dense_candidate_k=_env_int(
            "LOCAL_RAG_DENSE_CANDIDATE_K", DEFAULT_RAG_DENSE_CANDIDATE_K
        ),
        rag_sparse_candidate_k=_env_int(
            "LOCAL_RAG_SPARSE_CANDIDATE_K", DEFAULT_RAG_SPARSE_CANDIDATE_K
        ),
        rag_rrf_candidate_k=_env_int("LOCAL_RAG_RRF_CANDIDATE_K", DEFAULT_RAG_RRF_CANDIDATE_K),
        rag_rerank_candidate_k=_env_int(
            "LOCAL_RAG_RERANK_CANDIDATE_K", DEFAULT_RAG_RERANK_CANDIDATE_K
        ),
        rag_top_k=_env_int("LOCAL_RAG_TOP_K", DEFAULT_RAG_TOP_K),
        rag_rerank_enabled=_env_bool("LOCAL_RAG_RERANK_ENABLED", DEFAULT_RAG_RERANK_ENABLED),
        rag_project_max_chars=_env_int(
            "LOCAL_RAG_PROJECT_MAX_CHARS", DEFAULT_RAG_PROJECT_MAX_CHARS
        ),
        rag_project_max_chunks=_env_int(
            "LOCAL_RAG_PROJECT_MAX_CHUNKS", DEFAULT_RAG_PROJECT_MAX_CHUNKS
        ),
        rag_project_rerank_enabled=_env_bool(
            "LOCAL_RAG_PROJECT_RERANK_ENABLED",
            DEFAULT_RAG_PROJECT_RERANK_ENABLED,
        ),
        rag_rerank_model=os.getenv("LOCAL_RAG_RERANK_MODEL", DEFAULT_RAG_RERANK_MODEL),
        rag_hybrid_enabled=_env_bool("LOCAL_RAG_HYBRID_ENABLED", DEFAULT_RAG_HYBRID_ENABLED),
        rag_neighbor_expansion=_env_bool(
            "LOCAL_RAG_NEIGHBOR_EXPANSION", DEFAULT_RAG_NEIGHBOR_EXPANSION
        ),
        rag_neighbor_count=_env_int("LOCAL_RAG_NEIGHBOR_COUNT", DEFAULT_RAG_NEIGHBOR_COUNT),
        rag_query_preprocess_enabled=_env_bool(
            "LOCAL_RAG_QUERY_PREPROCESS_ENABLED",
            DEFAULT_RAG_QUERY_PREPROCESS_ENABLED,
        ),
        agent_temperature=_env_float("AGENT_TEMPERATURE", DEFAULT_AGENT_TEMPERATURE),
        agent_enable_thinking=_env_bool("AGENT_ENABLE_THINKING", DEFAULT_AGENT_ENABLE_THINKING),
        agent_reasoning_effort=os.getenv(
            "AGENT_REASONING_EFFORT", DEFAULT_AGENT_REASONING_EFFORT
        ).strip(),
        agent_llm_request_timeout=max(
            10.0,
            _env_float(
                "AGENT_LLM_REQUEST_TIMEOUT",
                DEFAULT_AGENT_LLM_REQUEST_TIMEOUT,
            ),
        ),
    )
