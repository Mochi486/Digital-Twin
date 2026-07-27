import os
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DATA_DIR = PROJECT_ROOT / "data"
RUNS_DIR = PROJECT_ROOT / "runs"
EVIDENCE_DIR = PROJECT_ROOT / ".local-evidence"
TESTS_DIR = PROJECT_ROOT / "tests"
DOCS_DIR = PROJECT_ROOT / "docs"


DEFAULT_PROVIDER = "mock"
DEFAULT_OPENAI_MODEL = "gpt-5.6"
DEFAULT_COMPATIBLE_MODELS = [
    "qwen3.7-max-2026-06-08",
    "qwen3.7-max",
    "deepseek-v4-pro",
    "qwen3.7-plus",
    "qwen3.6-flash",
]
OPENAI_PREFERRED_MODELS = [
    "gpt-5.6",
    "gpt-5",
    "gpt-4.1",
    "gpt-4o",
]


MAX_GENERATED_NODE_COUNT = 10
MIN_GENERATED_NODE_COUNT = 2
MAX_DELAY_MS = 250
MAX_PACKET_LOSS_PERCENT = 20
MAX_BANDWIDTH_MBPS = 1000
MAX_TRAFFIC_DURATION_S = 30
MAX_PING_COUNT = 10
MIN_BANDWIDTH_MBPS = 1


ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
ROLE_VALUES = {"client", "router", "server"}
PROTOCOL_VALUES = {"tcp"}


FORBIDDEN_STRING_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bdocker\b",
        r"\biptables\b",
        r"\bip\s+route\b",
        r"\broute\s+add\b",
        r"\broute\s+del\b",
        r"\broute\b",
        r"\bsubnet\b",
        r"\bpython(?:3)?\b",
        r"\bsh\b",
        r"\bbash\b",
        r"\bsudo\b",
        r"\btc\b",
        r"\b\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?\b",
        r";",
        r"\|\|",
        r"&&",
    )
]


SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]+"),
    re.compile(r"(OPENAI_API_KEY\s*=\s*)([^\s\"']+)", re.IGNORECASE),
    re.compile(r"(COMPAT_API_KEY\s*=\s*)([^\s\"']+)", re.IGNORECASE),
    re.compile(r"(Bearer\s+)([A-Za-z0-9._-]+)", re.IGNORECASE),
]


PROVIDER_ENV = {
    "openai": {
        "api_key": "OPENAI_API_KEY",
        "base_url": "",
        "default_model": DEFAULT_OPENAI_MODEL,
    },
    "openai_compatible": {
        "api_key": "COMPAT_API_KEY",
        "base_url": "COMPAT_BASE_URL",
        "model_candidates": "COMPAT_MODEL_CANDIDATES",
        "default_models": DEFAULT_COMPATIBLE_MODELS,
    },
}


CAPABILITY_ENDPOINTS = [
    "responses_json_schema",
    "chat_json_schema",
    "chat_json_object",
    "chat_plain_json",
]


DEFAULT_ADDRESSING = {
    "base_cidr": "10.64.0.0/16",
    "subnet_prefixlen": 29,
}


IMAGE_NAME = "my-iperf-tc"


API_RETRY_ATTEMPTS = 3
API_RETRY_BASE_DELAY_S = 1.0
API_RETRY_MAX_DELAY_S = 10.0
API_TIMEOUT_S = 120.0


LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_LEVEL = os.environ.get("DIGITAL_TWIN_LOG_LEVEL", "INFO").upper()


OPENAI_SYSTEM_PROMPT = """You generate abstract routed network scenarios as JSON only.
Return only nodes, links, and traffic plus per-link network conditions.
Do not generate shell, Docker, iptables, IP, subnet, route, or tc commands.
Keep the topology small and safe to run locally.
Use lowercase node ids with letters, digits, and dashes.
Prefer exactly one client, one server, and router nodes in between.
"""
