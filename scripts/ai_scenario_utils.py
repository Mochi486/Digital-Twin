import hashlib
import json
import re
from copy import deepcopy

from config import (
    FORBIDDEN_STRING_PATTERNS,
    ID_PATTERN,
    MAX_BANDWIDTH_MBPS,
    MAX_DELAY_MS,
    MAX_GENERATED_NODE_COUNT,
    MAX_PACKET_LOSS_PERCENT,
    MAX_PING_COUNT,
    MAX_TRAFFIC_DURATION_S,
    MIN_BANDWIDTH_MBPS,
    MIN_GENERATED_NODE_COUNT,
    OPENAI_SYSTEM_PROMPT,
    PROTOCOL_VALUES,
    ROLE_VALUES,
)
from logging_utils import get_logger
from topology_utils import build_graph_adjacency, validate_topology_scenario


logger = get_logger(__name__)


DEFAULT_PROVIDER = "mock"
DEFAULT_OPENAI_MODEL = "gpt-5.6"
DEFAULT_COMPATIBLE_MODELS = [
    "qwen3.7-max-2026-06-08",
    "qwen3.7-max",
    "deepseek-v4-pro",
    "qwen3.7-plus",
    "qwen3.6-flash",
]


def build_generation_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["nodes", "links", "traffic"],
        "properties": {
            "nodes": {
                "type": "array",
                "minItems": MIN_GENERATED_NODE_COUNT,
                "maxItems": MAX_GENERATED_NODE_COUNT,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["id", "role"],
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
                    "required": ["source", "target", "bandwidth_mbps", "delay_ms", "packet_loss_percent"],
                    "properties": {
                        "source": {"type": "string"},
                        "target": {"type": "string"},
                        "bandwidth_mbps": {"type": "number", "minimum": MIN_BANDWIDTH_MBPS, "maximum": MAX_BANDWIDTH_MBPS},
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
                    "duration_s": {"type": "integer", "minimum": 1, "maximum": MAX_TRAFFIC_DURATION_S},
                    "ping_count": {"type": "integer", "minimum": 1, "maximum": MAX_PING_COUNT},
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


def _append_error(errors: list[str], message: str) -> None:
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
        if "bandwidth_mbps" in link and not MIN_BANDWIDTH_MBPS <= float(link["bandwidth_mbps"]) <= MAX_BANDWIDTH_MBPS:
            _append_error(errors, f"links[{index}].bandwidth_mbps must be between {MIN_BANDWIDTH_MBPS} and {MAX_BANDWIDTH_MBPS}.")

    errors.extend(find_forbidden_content(candidate))

    return {"valid": not errors, "errors": errors}


def count_simple_paths(adjacency: dict[str, set[str]], source: str, destination: str, limit: int = 2) -> int:
    if source not in adjacency or destination not in adjacency:
        return 0

    path_count = 0
    stack = [(source, [source])]
    while stack:
        node_id, path = stack.pop()
        for neighbor in sorted(adjacency[node_id]):
            if neighbor in path:
                continue
            next_path = path + [neighbor]
            if neighbor == destination:
                path_count += 1
                if path_count >= limit:
                    return path_count
                continue
            stack.append((neighbor, next_path))
    return path_count


def validate_prompt_constraints(candidate: dict, prompt: str) -> dict:
    errors = []
    if not isinstance(candidate, dict):
        return {"valid": False, "errors": ["Scenario must be a JSON object."], "constraints": infer_prompt_constraints(prompt)}

    constraints = infer_prompt_constraints(prompt)
    nodes = candidate.get("nodes", [])
    links = candidate.get("links", [])
    traffic = candidate.get("traffic", {})

    if constraints.get("explicit_node_count") and len(nodes) != constraints["node_count"]:
        _append_error(errors, f"Scenario must contain exactly {constraints['node_count']} nodes; got {len(nodes)}.")

    for index, link in enumerate(links):
        if constraints.get("explicit_bandwidth") and float(link.get("bandwidth_mbps", -1)) != constraints["bandwidth_mbps"]:
            _append_error(
                errors,
                f"links[{index}].bandwidth_mbps must equal {constraints['bandwidth_mbps']}.",
            )
        if constraints.get("explicit_delay") and float(link.get("delay_ms", -1)) != constraints["delay_ms"]:
            _append_error(errors, f"links[{index}].delay_ms must equal {constraints['delay_ms']}.")
        if constraints.get("explicit_packet_loss") and float(link.get("packet_loss_percent", -1)) != constraints["packet_loss_percent"]:
            _append_error(
                errors,
                f"links[{index}].packet_loss_percent must equal {constraints['packet_loss_percent']}.",
            )

    if constraints["redundant"] and isinstance(nodes, list) and isinstance(links, list) and isinstance(traffic, dict):
        node_ids = [node.get("id") for node in nodes if isinstance(node, dict)]
        if traffic.get("source") in node_ids and traffic.get("destination") in node_ids:
            adjacency = build_graph_adjacency(node_ids, links)
            simple_path_count = count_simple_paths(adjacency, traffic["source"], traffic["destination"], limit=2)
            if simple_path_count < 2:
                _append_error(errors, "Topology must provide at least two alternative client-to-server paths.")

    return {"valid": not errors, "errors": errors, "constraints": constraints}


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
    prompt_constraint_validation = validate_prompt_constraints(candidate, prompt)
    projection_validation = {"valid": False, "errors": []}
    projected_scenario = None

    if schema_validation["valid"] and semantic_validation["valid"] and prompt_constraint_validation["valid"]:
        try:
            projected_scenario = build_projected_scenario(candidate, prompt, topology_name=topology_name)
            projection_validation = {"valid": True, "errors": []}
        except ValueError as exc:
            projection_validation = {"valid": False, "errors": [str(exc)]}

    overall_valid = (
        schema_validation["valid"]
        and semantic_validation["valid"]
        and prompt_constraint_validation["valid"]
        and projection_validation["valid"]
    )
    return {
        "valid": overall_valid,
        "schema_validation": schema_validation,
        "semantic_validation": semantic_validation,
        "prompt_constraint_validation": prompt_constraint_validation,
        "projection_validation": projection_validation,
        "projected_scenario": projected_scenario,
    }


def build_validation_gate_report(
    candidate: dict,
    prompt: str,
    topology_name: str | None = None,
    max_nodes: int = MAX_GENERATED_NODE_COUNT,
) -> dict:
    validation = validate_and_project_generated_scenario(
        candidate,
        prompt,
        topology_name=topology_name,
        max_nodes=max_nodes,
    )
    schema_errors = validation["schema_validation"]["errors"]
    semantic_errors = validation["semantic_validation"]["errors"]
    prompt_constraint_errors = validation["prompt_constraint_validation"]["errors"]
    projection_errors = validation["projection_validation"]["errors"]

    def _status(errors: list[str], predicate) -> str:
        return "passed" if not any(predicate(error) for error in errors) else "failed"

    gates = {
        "json_schema_validation": "passed" if validation["schema_validation"]["valid"] else "failed",
        "semantic_validation": "passed" if validation["semantic_validation"]["valid"] else "failed",
        "prompt_constraint_validation": "passed" if validation["prompt_constraint_validation"]["valid"] else "failed",
        "connected_topology_validation": _status(
            projection_errors,
            lambda error: "Topology is disconnected" in error or "No path between" in error,
        ),
        "duplicate_link_validation": _status(
            semantic_errors + projection_errors,
            lambda error: "Duplicate link detected" in error,
        ),
        "node_role_validation": _status(
            schema_errors + semantic_errors,
            lambda error: "role must be one of" in error
            or "exactly one client" in error
            or "exactly one server" in error
            or "traffic.source must be the client node" in error
            or "traffic.destination must be the server node" in error,
        ),
        "node_count_limit": _status(
            semantic_errors + prompt_constraint_errors,
            lambda error: "nodes count must be between" in error or "must contain exactly" in error,
        ),
        "six_node_constraint": _status(
            prompt_constraint_errors,
            lambda error: "must contain exactly" in error,
        ),
        "alternative_path_validation": _status(
            prompt_constraint_errors,
            lambda error: "alternative client-to-server paths" in error,
        ),
        "impairment_range_validation": _status(
            schema_errors + semantic_errors + prompt_constraint_errors + projection_errors,
            lambda error: "bandwidth_mbps" in error
            or "delay_ms" in error
            or "packet_loss_percent" in error,
        ),
        "forbidden_command_content_rejection": _status(
            semantic_errors,
            lambda error: "forbidden command-like content" in error,
        ),
        "deterministic_addressing": "passed" if validation["projected_scenario"] else "failed",
        "deterministic_static_route_generation": (
            "passed"
            if validation["projected_scenario"] and validation["projected_scenario"].get("generated_routes")
            else "failed"
        ),
        "route_conflict_detection": _status(
            projection_errors,
            lambda error: "Route conflict" in error,
        ),
    }

    return {
        "valid": validation["valid"],
        "gates": gates,
        "schema_validation": validation["schema_validation"],
        "semantic_validation": validation["semantic_validation"],
        "prompt_constraint_validation": validation["prompt_constraint_validation"],
        "projection_validation": validation["projection_validation"],
        "projected_scenario": validation["projected_scenario"],
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
    explicit_node_count = False
    match = re.search(r"\b(\d+)(?:\s*-\s*node|\s+node)\b", lowered)
    if match:
        count = int(match.group(1))
        explicit_node_count = True
    else:
        for word in ("two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"):
            if re.search(rf"\b{word}(?:\s*-\s*node|\s+node)\b", lowered):
                count = _word_to_int(word)
                explicit_node_count = True
                break
    if count is None:
        count = 5

    bandwidth_match = re.search(r"(\d+(?:\.\d+)?)\s*mbps", lowered)
    delay_match = re.search(r"(\d+(?:\.\d+)?)\s*ms", lowered)
    loss_match = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:packet\s*)?loss", lowered)

    return {
        "node_count": count,
        "explicit_node_count": explicit_node_count,
        "bandwidth_mbps": float(bandwidth_match.group(1)) if bandwidth_match else 20.0,
        "explicit_bandwidth": bool(bandwidth_match),
        "delay_ms": float(delay_match.group(1)) if delay_match else 0.0,
        "explicit_delay": bool(delay_match),
        "packet_loss_percent": float(loss_match.group(1)) if loss_match else 0.0,
        "explicit_packet_loss": bool(loss_match),
        "redundant": (
            "redundant" in lowered
            or "two path" in lowered
            or "candidate paths" in lowered
            or "alternative paths" in lowered
        ),
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
