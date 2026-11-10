"""Benchmark dataset for retrieval evaluation (P2-04).

Contains 35 realistic code search queries and ground-truth target files/symbols
evaluated over a reference Python codebase.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkQuery:
    query_id: str
    query: str
    expected_file: str
    expected_symbol: str | None = None
    category: str = "general"


BENCHMARK_CORPUS: dict[str, str] = {
    "auth/jwt.py": """\"\"\"JWT creation, verification, and decoding helpers.\"\"\"
import jwt
from datetime import datetime, timedelta, UTC

SECRET_KEY = "super-secret-key"
ALGORITHM = "HS256"

def create_access_token(user_id: str, expires_delta: timedelta | None = None) -> str:
    \"\"\"Encode a user id into a signed JWT bearer token.\"\"\"
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=30))
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> dict[str, str]:
    \"\"\"Decode and validate signature of an incoming JWT token.\"\"\"
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
""",
    "auth/password.py": """\"\"\"Password hashing and verification utilities using bcrypt.\"\"\"
import bcrypt

def hash_password(password: str) -> str:
    \"\"\"Salt and hash a plaintext password with bcrypt.\"\"\"
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    \"\"\"Compare a plaintext password against a stored bcrypt hash.\"\"\"
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
""",
    "database/connection.py": """\"\"\"Database engine initialization and async sessionmaker.\"\"\"
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/repopilot"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def check_database_health() -> bool:
    \"\"\"Ping the database to verify active connectivity.\"\"\"
    async with engine.connect() as conn:
        res = await conn.execute("SELECT 1")
        return bool(res.scalar())
""",
    "database/models.py": """\"\"\"SQLAlchemy models for core entities: Repository and CodeChunk.\"\"\"
import uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

class Base(DeclarativeBase):
    pass

class RepositoryModel(Base):
    __tablename__ = "repositories"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

class ChunkModel(Base):
    __tablename__ = "code_chunks"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id"))
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
""",
    "api/routes/auth.py": """\"\"\"FastAPI endpoints for authentication: login and token refresh.\"\"\"
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
async def login(req: LoginRequest):
    \"\"\"Authenticate credentials and return an access token.\"\"\"
    if req.username == "admin" and req.password == "secret":
        return {"access_token": "token123", "token_type": "bearer"}
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
""",
    "api/routes/repos.py": """\"\"\"Endpoints for repository registration and scan inspection.\"\"\"
from fastapi import APIRouter, status
import uuid

router = APIRouter(prefix="/repositories", tags=["repositories"])

@router.post("/")
async def register_repository(url: str):
    \"\"\"Register a new public GitHub repo for scanning.\"\"\"
    return {"repository_id": str(uuid.uuid4()), "url": url, "status": "pending"}

@router.get("/{repo_id}")
async def get_repository_details(repo_id: str):
    \"\"\"Retrieve stored metrics and status for a repository.\"\"\"
    return {"repository_id": repo_id, "status": "completed"}
""",
    "api/routes/search.py": """\"\"\"Semantic code search endpoint across vector embeddings.\"\"\"
from fastapi import APIRouter, Query

router = APIRouter(prefix="/search", tags=["search"])

@router.get("/")
async def search_code(q: str = Query(..., min_length=1), limit: int = 10):
    \"\"\"Retrieve top-k relevant code chunks matching natural language query.\"\"\"
    return {"query": q, "limit": limit, "results": []}
""",
    "parsing/treesitter.py": """\"\"\"Tree-sitter AST parser for extracting Python functions and classes.\"\"\"
import tree_sitter_python
from tree_sitter import Language, Parser

class ASTCodeParser:
    def __init__(self):
        self.language = Language(tree_sitter_python.language())
        self.parser = Parser(self.language)

    def extract_symbols(self, code: str) -> list[str]:
        \"\"\"Walk tree-sitter AST and collect function and class names.\"\"\"
        tree = self.parser.parse(code.encode("utf-8"))
        symbols = []
        cursor = tree.walk()
        # Traversal logic
        return symbols
""",
    "parsing/metrics.py": """\"\"\"Radon code metrics: LOC, Cyclomatic Complexity (CC), and Maintainability Index (MI).\"\"\"
from radon.complexity import cc_visit
from radon.metrics import mi_visit
from radon.raw import analyze

def compute_code_metrics(source_code: str) -> dict[str, float]:
    \"\"\"Calculate raw lines of code, cyclomatic complexity, and maintainability index.\"\"\"
    raw = analyze(source_code)
    cc_blocks = cc_visit(source_code)
    avg_cc = sum(b.complexity for b in cc_blocks) / max(1, len(cc_blocks))
    mi = mi_visit(source_code, multi=True)
    return {"loc": raw.loc, "sloc": raw.sloc, "cyclomatic_complexity": avg_cc, "maintainability_index": mi}
""",
    "repos/fetcher.py": """\"\"\"Safe repository fetching with git shallow clone and zip bomb protection.\"\"\"
import subprocess
from pathlib import Path

def shallow_clone_repo(git_url: str, target_dir: Path, timeout_seconds: int = 60) -> None:
    \"\"\"Perform shallow clone with depth 1, terminal prompt disabled, and hooks suppressed.\"\"\"
    cmd = ["git", "-c", "core.hooksPath=/dev/null", "clone", "--depth", "1", "--no-tags", git_url, str(target_dir)]
    subprocess.run(cmd, timeout=timeout_seconds, check=True)
""",
    "repos/filter.py": """\"\"\"File filter for pruning binaries, vendor dependencies, and secrets.\"\"\"
import re
from pathlib import Path

BINARY_EXTENSIONS = {".pyc", ".so", ".dll", ".exe", ".png", ".jpg", ".zip", ".tar"}
SECRET_PATTERN = re.compile(r"(?:AKIA[A-Z0-9]{16}|ghp_[a-zA-Z0-9]{36})")

def should_index_file(file_path: Path, content: str) -> bool:
    \"\"\"Determine whether a file should be accepted for indexing or rejected.\"\"\"
    if file_path.suffix in BINARY_EXTENSIONS:
        return False
    if SECRET_PATTERN.search(content):
        return False
    return True
""",
    "ai/chunker.py": """\"\"\"Symbol-aware and sliding window chunker for Python modules.\"\"\"
class SymbolAwareChunker:
    def __init__(self, max_chunk_chars: int = 1500, overlap_lines: int = 3):
        self.max_chunk_chars = max_chunk_chars
        self.overlap_lines = overlap_lines

    def chunk_python_module(self, code: str) -> list[dict]:
        \"\"\"Chunk source code preserving complete function bodies intact.\"\"\"
        # Chunker logic
        return []
""",
    "ai/embeddings.py": """\"\"\"Vector embedding provider interfaces and OpenAI batch implementation.\"\"\"
from abc import ABC, abstractmethod
import httpx

class BaseEmbeddingProvider(ABC):
    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        pass

class OpenAIEmbedder(BaseEmbeddingProvider):
    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self.api_key = api_key
        self.model = model

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        \"\"\"Send text batch to OpenAI /v1/embeddings REST API.\"\"\"
        return []
""",
    "ai/rag_pipeline.py": """\"\"\"Retrieval-Augmented Generation (RAG) assistant with source citations and abstention.\"\"\"
def format_rag_prompt(question: str, retrieved_chunks: list[dict]) -> str:
    \"\"\"Assemble prompt with evidence chunks and explicit citation instructions.\"\"\"
    if not retrieved_chunks:
        return "I do not have enough evidence to answer this question."
    context = "\\n\\n".join([f"[{c['file']}:{c['line']}] {c['text']}" for c in retrieved_chunks])
    return f"Context:\\n{context}\\n\\nQuestion: {question}\\nAnswer with citations:"
""",
    "worker/tasks.py": """\"\"\"Async background worker jobs for repository scanning and indexing.\"\"\"
async def scan_repository_job(ctx: dict, repository_id: str) -> dict:
    \"\"\"Execute full pipeline: fetch -> filter -> parse -> compute metrics -> chunk -> embed.\"\"\"
    return {"status": "completed", "repository_id": repository_id}
""",
    "worker/scheduler.py": """\"\"\"Periodic task scheduler and queue heartbeat monitor.\"\"\"
import asyncio

async def run_periodic_cleanup_job():
    \"\"\"Remove stale temporary directories and orphaned download artifacts.\"\"\"
    while True:
        await asyncio.sleep(3600)
""",
    "ml/defect_predict.py": """\"\"\"Machine learning defect prediction classifier using scikit-learn.\"\"\"
from sklearn.ensemble import RandomForestClassifier
import numpy as np

class DefectRiskPredictor:
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)

    def predict_risk(self, feature_vector: list[float]) -> float:
        \"\"\"Predict probability that a module contains software defects.\"\"\"
        probs = self.model.predict_proba([feature_vector])
        return float(probs[0][1])
""",
    "ml/features.py": """\"\"\"Feature engineering pipeline transforming code metrics into ML tensors.\"\"\"
def extract_feature_vector(loc: int, cc: float, halstead_volume: float, fan_in: int, fan_out: int) -> list[float]:
    \"\"\"Normalize and assemble code metrics for input into defect prediction models.\"\"\"
    return [float(loc), float(cc), float(halstead_volume), float(fan_in), float(fan_out)]
""",
    "static/ruff_runner.py": """\"\"\"Static code analysis runner wrapping Ruff linter execution.\"\"\"
import subprocess
import json

def run_ruff_linter(target_dir: str) -> list[dict]:
    \"\"\"Execute ruff check with JSON output format and parse violations.\"\"\"
    res = subprocess.run(["ruff", "check", "--format=json", target_dir], capture_output=True, text=True)
    return json.loads(res.stdout) if res.stdout else []
""",
    "graph/networkx_graph.py": """\"\"\"Dependency and module import graph builder using NetworkX.\"\"\"
import networkx as nx

def build_import_graph(modules_imports: dict[str, list[str]]) -> nx.DiGraph:
    \"\"\"Construct directed graph representing module dependencies and fan-in/fan-out.\"\"\"
    graph = nx.DiGraph()
    for mod, imports in modules_imports.items():
        graph.add_node(mod)
        for imp in imports:
            graph.add_edge(mod, imp)
    return graph
""",
    "graph/impact.py": """\"\"\"Change impact analysis via reverse reachability traversal.\"\"\"
import networkx as nx

def find_affected_modules(graph: nx.DiGraph, changed_module: str, max_depth: int = 3) -> set[str]:
    \"\"\"Find all downstream modules that depend directly or indirectly on changed_module.\"\"\"
    reversed_graph = graph.reverse()
    return set(nx.single_source_shortest_path_length(reversed_graph, changed_module, cutoff=max_depth).keys())
""",
    "core/config.py": """\"\"\"Application configuration loaded from environment variables.\"\"\"
from pydantic_settings import BaseSettings

class AppSettings(BaseSettings):
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/repopilot"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "secret"
""",
    "core/logging.py": """\"\"\"Structured JSON logging formatter with request correlation IDs.\"\"\"
import logging
import json

class JSONLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        \"\"\"Serialize log record into a single-line JSON string.\"\"\"
        payload = {"level": record.levelname, "message": record.getMessage(), "logger": record.name}
        return json.dumps(payload)
""",
    "core/security.py": """\"\"\"Security utilities: constant-time string comparison and secret redaction.\"\"\"
import hmac

def constant_time_compare(val_a: str, val_b: str) -> bool:
    \"\"\"Compare two strings in constant time to prevent timing attacks.\"\"\"
    return hmac.compare_digest(val_a.encode("utf-8"), val_b.encode("utf-8"))
""",
    "tests/conftest.py": """\"\"\"Pytest fixtures: test database session, fake redis, and mock client.\"\"\"
import pytest

@pytest.fixture
def mock_app_client():
    \"\"\"Yield test client for sending async HTTP requests to FastAPI.\"\"\"
    return None
""",
}


BENCHMARK_QUERIES: list[BenchmarkQuery] = [
    # Auth & Tokens (5)
    BenchmarkQuery(
        "Q01",
        "How are JWT bearer tokens signed and created?",
        "auth/jwt.py",
        "create_access_token",
        "auth",
    ),
    BenchmarkQuery(
        "Q02",
        "Validate and decode signature of incoming JWT access token",
        "auth/jwt.py",
        "decode_access_token",
        "auth",
    ),
    BenchmarkQuery(
        "Q03",
        "Bcrypt password hashing and salting",
        "auth/password.py",
        "hash_password",
        "auth",
    ),
    BenchmarkQuery(
        "Q04",
        "Verify plaintext password against bcrypt hash",
        "auth/password.py",
        "verify_password",
        "auth",
    ),
    BenchmarkQuery(
        "Q05",
        "FastAPI login endpoint credentials authentication",
        "api/routes/auth.py",
        "login",
        "auth",
    ),
    # Database & ORM (4)
    BenchmarkQuery(
        "Q06",
        "Database engine initialization and async sessionmaker",
        "database/connection.py",
        None,
        "database",
    ),
    BenchmarkQuery(
        "Q07",
        "Ping database connection health check",
        "database/connection.py",
        "check_database_health",
        "database",
    ),
    BenchmarkQuery(
        "Q08",
        "SQLAlchemy Base declarative model definition",
        "database/models.py",
        "Base",
        "database",
    ),
    BenchmarkQuery(
        "Q09",
        "Repository and CodeChunk entity table schema",
        "database/models.py",
        "RepositoryModel",
        "database",
    ),
    # API Routes (3)
    BenchmarkQuery(
        "Q10",
        "Register a new public GitHub repository endpoint",
        "api/routes/repos.py",
        "register_repository",
        "api",
    ),
    BenchmarkQuery(
        "Q11",
        "Retrieve repository status and metrics details",
        "api/routes/repos.py",
        "get_repository_details",
        "api",
    ),
    BenchmarkQuery(
        "Q12",
        "Semantic code search API route query",
        "api/routes/search.py",
        "search_code",
        "api",
    ),
    # Parsing & Metrics (4)
    BenchmarkQuery(
        "Q13",
        "Tree-sitter AST parser extracting Python functions and classes",
        "parsing/treesitter.py",
        "ASTCodeParser",
        "parsing",
    ),
    BenchmarkQuery(
        "Q14",
        "Walk tree-sitter AST cursor collecting symbols",
        "parsing/treesitter.py",
        "extract_symbols",
        "parsing",
    ),
    BenchmarkQuery(
        "Q15",
        "Compute radon cyclomatic complexity and maintainability index",
        "parsing/metrics.py",
        "compute_code_metrics",
        "metrics",
    ),
    BenchmarkQuery(
        "Q16",
        "Raw lines of code LOC and SLOC analysis",
        "parsing/metrics.py",
        "compute_code_metrics",
        "metrics",
    ),
    # Repository Ingestion (3)
    BenchmarkQuery(
        "Q17",
        "Git shallow clone with depth 1 and hooks disabled",
        "repos/fetcher.py",
        "shallow_clone_repo",
        "ingestion",
    ),
    BenchmarkQuery(
        "Q18",
        "Filter out binary files and vendor dependencies",
        "repos/filter.py",
        "should_index_file",
        "ingestion",
    ),
    BenchmarkQuery(
        "Q19",
        "Detect secret tokens and credentials in file content",
        "repos/filter.py",
        "should_index_file",
        "ingestion",
    ),
    # AI & Chunking (4)
    BenchmarkQuery(
        "Q20",
        "Symbol-aware code chunker preserving function bodies intact",
        "ai/chunker.py",
        "SymbolAwareChunker",
        "chunking",
    ),
    BenchmarkQuery(
        "Q21",
        "Vector embedding provider interface embed_texts",
        "ai/embeddings.py",
        "BaseEmbeddingProvider",
        "ai",
    ),
    BenchmarkQuery(
        "Q22",
        "OpenAI embedding batch REST API call",
        "ai/embeddings.py",
        "OpenAIEmbedder",
        "ai",
    ),
    BenchmarkQuery(
        "Q23",
        "RAG prompt formatting with source citations and abstention",
        "ai/rag_pipeline.py",
        "format_rag_prompt",
        "ai",
    ),
    # Background Worker (3)
    BenchmarkQuery(
        "Q24",
        "Background worker job for scanning repository",
        "worker/tasks.py",
        "scan_repository_job",
        "worker",
    ),
    BenchmarkQuery(
        "Q25",
        "Periodic cleanup job for removing stale temporary directories",
        "worker/scheduler.py",
        "run_periodic_cleanup_job",
        "worker",
    ),
    BenchmarkQuery(
        "Q26",
        "Redis worker job queue and task dispatch",
        "worker/tasks.py",
        None,
        "worker",
    ),
    # ML Defect Prediction (3)
    BenchmarkQuery(
        "Q27",
        "Predict probability of software defect risk using RandomForest",
        "ml/defect_predict.py",
        "predict_risk",
        "ml",
    ),
    BenchmarkQuery(
        "Q28",
        "Defect risk classifier model initialization",
        "ml/defect_predict.py",
        "DefectRiskPredictor",
        "ml",
    ),
    BenchmarkQuery(
        "Q29",
        "Extract code metric features into ML tensor vector",
        "ml/features.py",
        "extract_feature_vector",
        "ml",
    ),
    # Static Analysis & Graphs (4)
    BenchmarkQuery(
        "Q30",
        "Run ruff linter static code analysis with JSON output",
        "static/ruff_runner.py",
        "run_ruff_linter",
        "static",
    ),
    BenchmarkQuery(
        "Q31",
        "Build directed module import graph with NetworkX",
        "graph/networkx_graph.py",
        "build_import_graph",
        "graph",
    ),
    BenchmarkQuery(
        "Q32",
        "Change impact analysis reverse reachability downstream affected modules",
        "graph/impact.py",
        "find_affected_modules",
        "graph",
    ),
    BenchmarkQuery(
        "Q33",
        "Dependency graph fan-in and fan-out edges",
        "graph/networkx_graph.py",
        "build_import_graph",
        "graph",
    ),
    # Core & Security (2)
    BenchmarkQuery(
        "Q34",
        "Structured JSON logging formatter with request details",
        "core/logging.py",
        "JSONLogFormatter",
        "core",
    ),
    BenchmarkQuery(
        "Q35",
        "Constant-time string comparison preventing timing attacks",
        "core/security.py",
        "constant_time_compare",
        "security",
    ),
]
