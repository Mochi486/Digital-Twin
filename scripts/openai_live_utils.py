import json
import os
import re
import time
from urllib.parse import urlparse

from ai_scenario_utils import (
    DEFAULT_COMPATIBLE_MODELS,
    DEFAULT_OPENAI_MODEL,
    build_generation_schema,
    build_openai_text_format,
    extract_json_object,
    validate_generated_schema,
)


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
OPENAI_PREFERRED_MODELS = [
    "gpt-5.6",
    "gpt-5",
    "gpt-4.1",
    "gpt-4o",
]
CAPABILITY_ENDPOINTS = [
    "responses_json_schema",
    "chat_json_schema",
    "chat_json_object",
    "chat_plain_json",
]
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]+"),
    re.compile(r"(OPENAI_API_KEY\s*=\s*)([^\s\"']+)", re.IGNORECASE),
    re.compile(r"(COMPAT_API_KEY\s*=\s*)([^\s\"']+)", re.IGNORECASE),
    re.compile(r"(Bearer\s+)([A-Za-z0-9._-]+)", re.IGNORECASE),
]


def redact_text(value: str) -> str:
    redacted = value
    for pattern in SECRET_PATTERNS:
        if pattern.groups >= 1:
            redacted = pattern.sub(r"\1[REDACTED]", redacted)
        else:
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def redact_data(value):
    if isinstance(value, dict):
        return {key: redact_data(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_data(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def sanitize_provider_host(base_url: str | None) -> str | None:
    if not base_url:
        return None
    parsed = urlparse(base_url.strip())
    if not parsed.netloc:
        return None
    return parsed.netloc.lower()


def is_absolute_http_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def resolve_openai_model(cli_model: str | None = None) -> str:
    env_model = os.environ.get("OPENAI_MODEL", "").strip()
    if env_model:
        return env_model
    if cli_model and cli_model.strip():
        return cli_model.strip()
    return DEFAULT_OPENAI_MODEL


def resolve_provider_model(provider: str, cli_model: str | None = None) -> str:
    if provider == "openai":
        return resolve_openai_model(cli_model)
    if cli_model and cli_model.strip():
        return cli_model.strip()
    return parse_compatible_model_candidates(os.environ.get("COMPAT_MODEL_CANDIDATES", ""))[0]


def parse_compatible_model_candidates(value: str | None) -> list[str]:
    if not value:
        return list(DEFAULT_COMPATIBLE_MODELS)
    raw_items = [item.strip() for item in re.split(r"[\s,;]+", value) if item.strip()]
    ordered = []
    for candidate in DEFAULT_COMPATIBLE_MODELS + raw_items:
        if candidate not in ordered:
            ordered.append(candidate)
    return ordered


def get_openai_sdk():
    try:
        import openai
        from openai import OpenAI
    except ImportError:
        return None, {
            "installed": False,
            "version": None,
            "error_type": "import_error",
            "error_message": "The official openai Python SDK is not installed.",
        }
    return OpenAI, {
        "installed": True,
        "version": getattr(openai, "__version__", "unknown"),
        "error_type": None,
        "error_message": None,
    }


def create_provider_client(
    provider: str,
    api_key_override: str | None = None,
    base_url_override: str | None = None,
):
    env_config = PROVIDER_ENV[provider]
    api_key_env = env_config["api_key"]
    api_key = (api_key_override if api_key_override is not None else os.environ.get(api_key_env, "")).strip()
    if not api_key:
        return None, {
            "installed": None,
            "version": None,
            "error_type": "missing_api_key",
            "error_message": f"{api_key_env} is not set.",
            "provider": provider,
            "sanitized_host": sanitize_provider_host(base_url_override or os.environ.get(env_config.get("base_url", ""), "")),
        }
    openai_class, sdk_status = get_openai_sdk()
    if openai_class is None:
        return None, sdk_status

    client_kwargs = {"api_key": api_key}
    base_url_env = env_config.get("base_url", "")
    base_url = (base_url_override if base_url_override is not None else os.environ.get(base_url_env, "")).strip()
    if provider == "openai_compatible" and not is_absolute_http_url(base_url):
        return None, {
            **sdk_status,
            "provider": provider,
            "sanitized_host": sanitize_provider_host(base_url),
            "base_url_configured": bool(base_url),
            "error_type": "invalid_base_url",
            "error_message": f"{base_url_env} must be an absolute http(s) URL.",
        }
    if base_url:
        client_kwargs["base_url"] = base_url
    return openai_class(**client_kwargs), {
        **sdk_status,
        "provider": provider,
        "sanitized_host": sanitize_provider_host(base_url),
        "base_url_configured": bool(base_url),
    }


def is_model_access_error(error_type: str | None, status_code: int | None, error_message: str | None) -> bool:
    if error_type in {"model_not_found", "permission_denied"}:
        return True
    if status_code in {403, 404}:
        return True
    lowered = (error_message or "").lower()
    return "model" in lowered and ("not found" in lowered or "not have access" in lowered or "access" in lowered)


def list_accessible_models(client) -> dict:
    started_at = time.perf_counter()
    try:
        response = client.models.list()
        payload = response.model_dump() if hasattr(response, "model_dump") else response
        model_ids = sorted(item["id"] for item in payload.get("data", []) if isinstance(item, dict) and item.get("id"))
        return {
            "status": "ok",
            "model_ids": model_ids,
            "latency_seconds": round(time.perf_counter() - started_at, 3),
            "raw_response": redact_data(payload),
        }
    except Exception as exc:  # pragma: no cover
        return {
            "status": "error",
            "error_type": exc.__class__.__name__,
            "status_code": getattr(exc, "status_code", None),
            "error_message": redact_text(str(exc)),
            "latency_seconds": round(time.perf_counter() - started_at, 3),
        }


def choose_fallback_model(accessible_models: list[str]) -> str | None:
    for candidate in OPENAI_PREFERRED_MODELS:
        if candidate in accessible_models:
            return candidate
    for model_id in accessible_models:
        if model_id.startswith("gpt-5") or model_id.startswith("gpt-4.1") or model_id.startswith("gpt-4o"):
            return model_id
    return None


def _extract_response_text(payload: dict) -> str | None:
    raw_output_text = payload.get("output_text")
    if isinstance(raw_output_text, str) and raw_output_text.strip():
        return raw_output_text
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                return content["text"]
    return None


def _extract_chat_text(payload: dict) -> str | None:
    choices = payload.get("choices", [])
    if not choices:
        return None
    message = choices[0].get("message", {})
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_fragments = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                text_fragments.append(item["text"])
        if text_fragments:
            return "".join(text_fragments)
    return None


def _build_error_result(exc: Exception, endpoint_type: str, model: str, latency_seconds: float) -> dict:
    error_payload = None
    response_obj = getattr(exc, "response", None)
    if response_obj is not None and hasattr(response_obj, "json"):
        try:
            error_payload = response_obj.json()
        except Exception:
            error_payload = None
    return {
        "status": "error",
        "model": model,
        "endpoint_type": endpoint_type,
        "error_type": exc.__class__.__name__,
        "status_code": getattr(exc, "status_code", None),
        "error_message": redact_text(str(exc)),
        "error_payload": redact_data(error_payload) if error_payload is not None else None,
        "latency_seconds": round(latency_seconds, 3),
    }


def _normalize_usage(payload: dict) -> dict | None:
    usage = payload.get("usage")
    return redact_data(usage) if usage is not None else None


def _build_structured_result(payload: dict, raw_text: str | None, endpoint_type: str, model: str, latency_seconds: float) -> dict:
    if not raw_text:
        return {
            "status": "parse_error",
            "model": model,
            "endpoint_type": endpoint_type,
            "response_id": payload.get("id"),
            "request_timestamp": payload.get("created_at"),
            "usage": _normalize_usage(payload),
            "raw_response": redact_data(payload),
            "error_type": "structured_output_parse_error",
            "status_code": None,
            "error_message": "Could not extract JSON text from the provider response.",
            "latency_seconds": round(latency_seconds, 3),
        }

    try:
        candidate = extract_json_object(raw_text)
    except Exception as exc:
        return {
            "status": "parse_error",
            "model": model,
            "endpoint_type": endpoint_type,
            "response_id": payload.get("id"),
            "request_timestamp": payload.get("created_at"),
            "usage": _normalize_usage(payload),
            "raw_response": redact_data(payload),
            "raw_text": redact_text(raw_text),
            "error_type": exc.__class__.__name__,
            "status_code": None,
            "error_message": redact_text(str(exc)),
            "latency_seconds": round(latency_seconds, 3),
        }

    return {
        "status": "ok",
        "model": model,
        "endpoint_type": endpoint_type,
        "response_id": payload.get("id"),
        "request_timestamp": payload.get("created_at"),
        "usage": _normalize_usage(payload),
        "raw_response": redact_data(payload),
        "raw_text": redact_text(raw_text),
        "structured_output": candidate,
        "latency_seconds": round(latency_seconds, 3),
    }


def request_structured_scenario(client, prompt: str, model: str, system_prompt: str, endpoint_type: str) -> dict:
    started_at = time.perf_counter()
    schema = build_generation_schema()
    try:
        if endpoint_type == "responses_json_schema":
            response = client.responses.create(
                model=model,
                input=[
                    {
                        "role": "system",
                        "content": [{"type": "input_text", "text": system_prompt}],
                    },
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": prompt}],
                    },
                ],
                text={"format": build_openai_text_format()},
            )
            payload = response.model_dump() if hasattr(response, "model_dump") else response
            return _build_structured_result(
                payload,
                _extract_response_text(payload),
                endpoint_type,
                model,
                time.perf_counter() - started_at,
            )

        if endpoint_type == "chat_json_schema":
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "network_scenario",
                        "strict": True,
                        "schema": schema,
                    },
                },
            )
            payload = response.model_dump() if hasattr(response, "model_dump") else response
            return _build_structured_result(
                payload,
                _extract_chat_text(payload),
                endpoint_type,
                model,
                time.perf_counter() - started_at,
            )

        if endpoint_type == "chat_json_object":
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"{prompt}\n\nReturn one JSON object only. Do not wrap it in markdown."
                        ),
                    },
                ],
                response_format={"type": "json_object"},
            )
            payload = response.model_dump() if hasattr(response, "model_dump") else response
            return _build_structured_result(
                payload,
                _extract_chat_text(payload),
                endpoint_type,
                model,
                time.perf_counter() - started_at,
            )

        if endpoint_type == "chat_plain_json":
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"{prompt}\n\nReturn only valid JSON matching the requested structure. No markdown."
                        ),
                    },
                ],
            )
            payload = response.model_dump() if hasattr(response, "model_dump") else response
            return _build_structured_result(
                payload,
                _extract_chat_text(payload),
                endpoint_type,
                model,
                time.perf_counter() - started_at,
            )

        raise ValueError(f"Unsupported endpoint_type: {endpoint_type}")
    except Exception as exc:  # pragma: no cover
        return _build_error_result(exc, endpoint_type, model, time.perf_counter() - started_at)


def build_capability_probe_prompt() -> str:
    return (
        "Return a minimal connected two-node routed network JSON with one client, one server, "
        "20 Mbps bandwidth, 0 ms delay, 0 percent packet loss, and one TCP flow."
    )


def probe_model_capabilities(client, model: str, system_prompt: str) -> list[dict]:
    rows = []
    for endpoint_type in CAPABILITY_ENDPOINTS:
        result = request_structured_scenario(
            client,
            build_capability_probe_prompt(),
            model,
            system_prompt,
            endpoint_type,
        )
        schema_validation = None
        if result["status"] == "ok":
            schema_validation = validate_generated_schema(result["structured_output"])
            if not schema_validation["valid"]:
                result = {
                    **result,
                    "status": "parse_error",
                    "error_type": "schema_validation_failed",
                    "error_message": "; ".join(schema_validation["errors"]),
                }
        rows.append(
            {
                "model": model,
                "model_exists": True,
                "endpoint_type": endpoint_type,
                "json_schema_support": endpoint_type in {"responses_json_schema", "chat_json_schema"} and result["status"] == "ok",
                "json_object_support": endpoint_type == "chat_json_object" and result["status"] == "ok",
                "request_status": result["status"],
                "status_code": result.get("status_code"),
                "error_type": result.get("error_type"),
                "error_message": result.get("error_message"),
                "latency_seconds": result.get("latency_seconds"),
                "response_id": result.get("response_id"),
                "usage": result.get("usage"),
                "selected": False,
                "probe_result": redact_data(result),
            }
        )
        if result["status"] == "ok":
            break
    return rows


def is_reliably_structured_endpoint(endpoint_type: str) -> bool:
    return endpoint_type in {"responses_json_schema", "chat_json_schema", "chat_json_object"}


def model_exists(model: str, accessible_models: list[str]) -> bool:
    return model in accessible_models


def dump_json_text(value) -> str:
    return json.dumps(redact_data(value), indent=2) + "\n"
