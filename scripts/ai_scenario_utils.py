import hashlib
import json
import re
from copy import deepcopy

from topology_utils import validate_topology_scenario


DEFAULT_PROVIDER = "mock"
DEFAULT_OPENAI_MODEL = "gpt-5.6"
MAX_GENERATED_NODE_COUNT = 10
MIN_GENERATED_NODE_COUNT = 2
MAX_DELAY_MS = 250
MAX_PACKET_LOSS_PERCENT = 20
MAX_BANDWIDTH_MBPS = 1000
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
        r"\bsh\b",
        r"\bbash\b",
        r"\bsudo\b",
        r"\btc\b",
        r";",
        r"\|\|",
        r"&&",
    )
]

OPENAI_SYSTEM_PROMPT = """You generate abstract routed network scenarios as JSON only.
Return only nodes, links, and traffic plus per-link network conditions.
Do not generate shell, Docker, iptables, IP, subnet, route, or tc commands.
Keep the topology small and safe to run locally.
Use lowercase node ids with letters, digits, and dashes.
Prefer exactly one client, one server, and router nodes in between.
"""


def build_generation_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["nodes", "links", "traffic"],
        "properties": {
            "nodes": {
                "type": "array",
                "minItems": 2,
                "maxItems": MAX_GENERATED_NODE_COUNT,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["id"],
                    "properties": {
                        "id": {"type": "string"},
                        "role": {"type": "string", "enum": sorted(ROLE_VALUES)},
                    },
                },
            },
            "links": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["source", "target"],
                    "properties": {
                        "source": {"type": "string"},
                        "target": {"type": "string"},
                        "bandwidth_mbps": {"type": "number", "minimum": 1, "maximum": MAX_BANDWIDTH_MBPS},
                        "delay_ms": {"type": "number", "minimum": 0, "maximum": MAX_DELAY_MS},
                        "packet_loss_percent": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": MAX_PACKET_LOSS_PERCENT,
                        },
                    },
                },
            },
            "traffic": {
                "type": "object",
                "additionalProperties": False,
                "required": ["source", "destination", "protocol", "duration_s", "ping_count", "reverse"],
                "properties": {
                    "source": {"type": "string"},
                    "destination": {"type": "string"},
                    "protocol": {"type": "string", "enum": sorted(PROTOCOL_VALUES)},
                    "duration_s": {"type": "integer", "minimum": 1, "maximum": 30},
                    "ping_count": {"type": "integer", "minimum": 1, "maximum": 10},
                    "reverse": {"type": "boolean"},
                },
            },
        },
    }


def build_openai_text_format() -> dict:
    return {
        "type": "json_schema",
        "name": "network_scenario",
        "strict": True,
        "schema": build_generation_schema(),
    }


def _append_error(errors: list[str], message: str):
    errors.append(message)


def _expect_type(value, expected_type, path: str, errors: list[str]) -> bool:
    if not isinstance(value, expected_type):
        _append_error(errors, f"{path} must be {expected_type.__name__}.")
        return False
    return True


def validate_generated_schema(candidate) -> dict:
    errors = []
    if not isinstance(candidate, dict):
        return {"valid": False, "errors": ["Scenario must be a JSON object."]}

    allowed_top_level = {"nodes", "links", "traffic"}
    extra_fields = sorted(set(candidate) - allowed_top_level)
    if extra_fields:
        _append_error(errors, f"Unsupported top-level fields: {', '.join(extra_fields)}")

    nodes = candidate.get("nodes")
    links = candidate.get("links")
    traffic = candidate.get("traffic")

    if not _expect_type(nodes, list, "nodes", errors):
        nodes = []
    if not _expect_type(links, list, "links", errors):
        links = []
    if not _expect_type(traffic, dict, "traffic", errors):
        traffic = {}

    for index, node in enumerate(nodes):
        path = f"nodes[{index}]"
        if not _expect_type(node, dict, path, errors):
            continue
        extra_fields = sorted(set(node) - {"id", "role"})
        if extra_fields:
            _append_error(errors, f"{path} has unsupported fields: {', '.join(extra_fields)}")
        if "id" not in node or not isinstance(node["id"], str):
            _append_error(errors, f"{path}.id must be a string.")
        if "role" in node and node["role"] not in ROLE_VALUES:
            _append_error(errors, f"{path}.role must be one of {', '.join(sorted(ROLE_VALUES))}.")

    for index, link in enumerate(links):
        path = f"links[{index}]"
        if not _expect_type(link, dict, path, errors):
            continue
        extra_fields = sorted(set(link) - {"source", "target", "bandwidth_mbps", "delay_ms", "packet_loss_percent"})
        if extra_fields:
            _append_error(errors, f"{path} has unsupported fields: {', '.join(extra_fields)}")
        for field in ("source", "target"):
            if field not in link or not isinstance(link[field], str):
                _append_error(errors, f"{path}.{field} must be a string.")
        for field in ("bandwidth_mbps", "delay_ms", "packet_loss_percent"):
            if field in link and not isinstance(link[field], (int, float)):
                _append_error(errors, f"{path}.{field} must be numeric.")

    if isinstance(traffic, dict):
        extra_fields = sorted(set(traffic) - {"source", "destination", "protocol", "duration_s", "ping_count", "reverse"})
        if extra_fields:
            _append_error(errors, f"traffic has unsupported fields: {', '.join(extra_fields)}")
        required = ("source", "destination", "protocol", "duration_s", "ping_count", "reverse")
        for field in required:
            if field not in traffic:
                _append_error(errors, f"traffic.{field} is required.")
        for field in ("source", "destination", "protocol"):
            if field in traffic and not isinstance(traffic[field], str):
                _append_error(errors, f"traffic.{field} must be a string.")
        for field in ("duration_s", "ping_count"):
            if field in traffic and not isinstance(traffic[field], int):
                _append_error(errors, f"traffic.{field} must be an integer.")
        if "reverse" in traffic and not isinstance(traffic["reverse"], bool):
            _append_error(errors, "traffic.reverse must be a boolean.")

    return {"valid": not errors, "errors": errors}


def find_forbidden_content(candidate, path: str = "$") -> list[str]:
    findings = []
    if isinstance(candidate, dict):
        for key, value in candidate.items():
            findings.extend(find_forbidden_content(value, f"{path}.{key}"))
    elif isinstance(candidate, list):
        for index, value in enumerate(candidate):
            findings.extend(find_forbidden_content(value, f"{path}[{index}]"))
    elif isinstance(candidate, str):
        for pattern in FORBIDDEN_STRING_PATTERNS:
            if pattern.search(candidate):
                findings.append(f"{path} contains forbidden command-like content matching '{pattern.pattern}'.")
                break
    return findings


def _normalized_role_map(nodes: list[dict], traffic: dict) -> dict[str, str]:
    roles = {}
    source = traffic["source"]
    destination = traffic["destination"]
    for node in nodes:
        if "role" in node:
            roles[node["id"]] = node["role"]
        elif node["id"] == source:
            roles[node["id"]] = "client"
        elif node["id"] == destination:
            roles[node["id"]] = "server"
        else:
            roles[node["id"]] = "router"
    return roles


def validate_generated_semantics(candidate: dict, max_nodes: int = MAX_GENERATED_NODE_COUNT) -> dict:
    errors = []
    if not isinstance(candidate, dict):
        return {"valid": False, "errors": ["Scenario must be a JSON object."]}

    nodes = candidate.get("nodes", [])
    links = candidate.get("links", [])
    traffic = candidate.get("traffic", {})

    if not (MIN_GENERATED_NODE_COUNT <= len(nodes) <= max_nodes):
        _append_error(
            errors,
            f"nodes count must be between {MIN_GENERATED_NODE_COUNT} and {max_nodes}; got {len(nodes)}.",
        )

    node_ids = []
    for node in nodes:
        node_id = node.get("id")
        if isinstance(node_id, str):
            node_ids.append(node_id)
            if not ID_PATTERN.fullmatch(node_id):
                _append_error(errors, f"Invalid node id '{node_id}'. Use lowercase letters, digits, and dashes.")

    duplicate_ids = sorted({node_id for node_id in node_ids if node_ids.count(node_id) > 1})
    if duplicate_ids:
        _append_error(errors, f"Duplicate node ids: {', '.join(duplicate_ids)}")

    if len(set(node_ids)) != len(node_ids):
        pass

    if traffic.get("protocol") not in PROTOCOL_VALUES:
        _append_error(errors, f"traffic.protocol must be one of {', '.join(sorted(PROTOCOL_VALUES))}.")

    source = traffic.get("source")
    destination = traffic.get("destination")
    if source == destination and source is not None:
        _append_error(errors, "traffic.source and traffic.destination must be different nodes.")
    known_nodes = set(node_ids)
    for endpoint_field, endpoint_value in (("source", source), ("destination", destination)):
        if endpoint_value not in known_nodes:
            _append_error(errors, f"traffic.{endpoint_field} must reference a known node.")

    role_map = _normalized_role_map(nodes, traffic) if source in known_nodes and destination in known_nodes else {}
    if role_map:
        role_counts = {role: list(role_map.values()).count(role) for role in ROLE_VALUES}
        if role_counts["client"] != 1:
            _append_error(errors, f"Scenario must contain exactly one client; got {role_counts['client']}.")
        if role_counts["server"] != 1:
            _append_error(errors, f"Scenario must contain exactly one server; got {role_counts['server']}.")
        if role_map.get(source) != "client":
            _append_error(errors, "traffic.source must be the client node.")
        if role_map.get(destination) != "server":
            _append_error(errors, "traffic.destination must be the server node.")

    link_pairs = set()
    for index, link in enumerate(links):
        source_id = link.get("source")
        target_id = link.get("target")
        if source_id == target_id and source_id is not None:
            _append_error(errors, f"links[{index}] must not be a self-link.")
        if source_id not in known_nodes or target_id not in known_nodes:
            _append_error(errors, f"links[{index}] references unknown nodes.")
            continue
        pair = tuple(sorted((source_id, target_id)))
        if pair in link_pairs:
            _append_error(errors, f"Duplicate link detected between {pair[0]} and {pair[1]}.")
        link_pairs.add(pair)
        if "delay_ms" in link and not 0 <= float(link["delay_ms"]) <= MAX_DELAY_MS:
            _append_error(errors, f"links[{index}].delay_ms must be between 0 and {MAX_DELAY_MS}.")
        if "packet_loss_percent" in link and not 0 <= float(link["packet_loss_percent"]) <= MAX_PACKET_LOSS_PERCENT:
            _append_error(
                errors,
                f"links[{index}].packet_loss_percent must be between 0 and {MAX_PACKET_LOSS_PERCENT}.",
            )
        if "bandwidth_mbps" in link and not 1 <= float(link["bandwidth_mbps"]) <= MAX_BANDWIDTH_MBPS:
            _append_error(errors, f"links[{index}].bandwidth_mbps must be between 1 and {MAX_BANDWIDTH_MBPS}.")

    errors.extend(find_forbidden_content(candidate))

    return {"valid": not errors, "errors": errors}


def build_projected_scenario(candidate: dict, prompt: str, topology_name: str | None = None) -> dict:
    projected = {
        "topology_name": topology_name or default_topology_name(prompt),
        "nodes": [],
        "links": [],
        "traffic": deepcopy(candidate["traffic"]),
        "generation_metadata": {
            "origin": "ai-generated",
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        },
    }

    role_map = _normalized_role_map(candidate["nodes"], candidate["traffic"])
    for node in candidate["nodes"]:
        projected["nodes"].append({"id": node["id"], "type": role_map[node["id"]]})

    for link in candidate["links"]:
        normalized_link = {
            "source": link["source"],
            "target": link["target"],
            "delay_ms": float(link.get("delay_ms", 0)),
            "packet_loss_percent": float(link.get("packet_loss_percent", 0)),
        }
        if "bandwidth_mbps" in link:
            normalized_link["bandwidth_mbps"] = float(link["bandwidth_mbps"])
        projected["links"].append(normalized_link)

    return validate_topology_scenario(projected)


def validate_and_project_generated_scenario(
    candidate: dict,
    prompt: str,
    topology_name: str | None = None,
    max_nodes: int = MAX_GENERATED_NODE_COUNT,
) -> dict:
    schema_validation = validate_generated_schema(candidate)
    semantic_validation = validate_generated_semantics(candidate, max_nodes=max_nodes)
    projection_validation = {"valid": False, "errors": []}
    projected_scenario = None

    if schema_validation["valid"] and semantic_validation["valid"]:
        try:
            projected_scenario = build_projected_scenario(candidate, prompt, topology_name=topology_name)
            projection_validation = {"valid": True, "errors": []}
        except ValueError as exc:
            projection_validation = {"valid": False, "errors": [str(exc)]}

    overall_valid = (
        schema_validation["valid"]
        and semantic_validation["valid"]
        and projection_validation["valid"]
    )
    return {
        "valid": overall_valid,
        "schema_validation": schema_validation,
        "semantic_validation": semantic_validation,
        "projection_validation": projection_validation,
        "projected_scenario": projected_scenario,
    }


def default_topology_name(prompt: str) -> str:
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:10]
    return f"ai-scenario-{digest}"


def _word_to_int(token: str) -> int | None:
    table = {
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }
    return table.get(token.lower())


def infer_prompt_constraints(prompt: str) -> dict:
    lowered = prompt.lower()
    count = None
    match = re.search(r"\b(\d+)(?:\s*-\s*node|\s+node)\b", lowered)
    if match:
        count = int(match.group(1))
    else:
        for word in ("two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"):
            if re.search(rf"\b{word}(?:\s*-\s*node|\s+node)\b", lowered):
                count = _word_to_int(word)
                break
    if count is None:
        count = 5

    bandwidth_match = re.search(r"(\d+(?:\.\d+)?)\s*mbps", lowered)
    delay_match = re.search(r"(\d+(?:\.\d+)?)\s*ms", lowered)
    loss_match = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:packet\s*)?loss", lowered)

    return {
        "node_count": count,
        "bandwidth_mbps": float(bandwidth_match.group(1)) if bandwidth_match else 20.0,
        "delay_ms": float(delay_match.group(1)) if delay_match else 0.0,
        "packet_loss_percent": float(loss_match.group(1)) if loss_match else 0.0,
        "redundant": "redundant" in lowered or "two path" in lowered or "candidate paths" in lowered,
        "linear": "linear" in lowered or "chain" in lowered,
    }


def _build_linear_topology(node_count: int, bandwidth_mbps: float, delay_ms: float, packet_loss_percent: float) -> dict:
    nodes = []
    links = []
    for index in range(node_count):
        node_id = f"node-{index + 1}"
        if index == 0:
            role = "client"
        elif index == node_count - 1:
            role = "server"
        else:
            role = "router"
        nodes.append({"id": node_id, "role": role})
        if index > 0:
            links.append(
                {
                    "source": f"node-{index}",
                    "target": node_id,
                    "bandwidth_mbps": bandwidth_mbps,
                    "delay_ms": delay_ms,
                    "packet_loss_percent": packet_loss_percent,
                }
            )
    return {
        "nodes": nodes,
        "links": links,
        "traffic": {
            "source": "node-1",
            "destination": f"node-{node_count}",
            "protocol": "tcp",
            "duration_s": 2,
            "ping_count": 4,
            "reverse": True,
        },
    }


def _build_redundant_topology(node_count: int, bandwidth_mbps: float, delay_ms: float, packet_loss_percent: float) -> dict:
    base = _build_linear_topology(node_count, bandwidth_mbps, delay_ms, packet_loss_percent)
    if node_count < 6:
        raise ValueError("Redundant topology requires at least 6 nodes.")
    base["links"] = [
        {
            "source": "node-1",
            "target": "node-2",
            "bandwidth_mbps": bandwidth_mbps,
            "delay_ms": delay_ms,
            "packet_loss_percent": packet_loss_percent,
        },
        {
            "source": "node-2",
            "target": "node-4",
            "bandwidth_mbps": bandwidth_mbps,
            "delay_ms": delay_ms,
            "packet_loss_percent": packet_loss_percent,
        },
        {
            "source": "node-1",
            "target": "node-3",
            "bandwidth_mbps": bandwidth_mbps,
            "delay_ms": delay_ms,
            "packet_loss_percent": packet_loss_percent,
        },
        {
            "source": "node-3",
            "target": "node-4",
            "bandwidth_mbps": bandwidth_mbps,
            "delay_ms": delay_ms,
            "packet_loss_percent": packet_loss_percent,
        },
    ]
    for index in range(4, node_count):
        base["links"].append(
            {
                "source": f"node-{index}",
                "target": f"node-{index + 1}",
                "bandwidth_mbps": bandwidth_mbps,
                "delay_ms": delay_ms,
                "packet_loss_percent": packet_loss_percent,
            }
        )
    return base


def mock_generate_abstract_scenario(prompt: str) -> tuple[dict, str]:
    constraints = infer_prompt_constraints(prompt)
    if constraints["redundant"]:
        scenario = _build_redundant_topology(
            constraints["node_count"],
            constraints["bandwidth_mbps"],
            constraints["delay_ms"],
            constraints["packet_loss_percent"],
        )
    else:
        scenario = _build_linear_topology(
            constraints["node_count"],
            constraints["bandwidth_mbps"],
            constraints["delay_ms"],
            constraints["packet_loss_percent"],
        )
    raw_response = json.dumps(scenario, indent=2)
    return scenario, raw_response


def extract_json_object(payload) -> dict:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        return json.loads(payload)
    raise ValueError("Provider response was not a JSON object or JSON string.")
