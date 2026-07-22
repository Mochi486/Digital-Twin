"""Deterministic, bounded Germany50 selected-path scenario definitions."""

from copy import deepcopy
from pathlib import Path

from topology_utils import find_link_between, validate_topology_scenario


PATHS = {
    "shortest": ["aachen", "koeln"],
    "median": ["erfurt", "wuerzburg", "augsburg", "muenchen", "passau"],
    "longest": [
        "oldenburg", "bremen", "hannover", "braunschweig", "kassel", "erfurt",
        "wuerzburg", "augsburg", "muenchen", "passau",
    ],
}
CONFIG = {
    "bandwidth_mbps": 20,
    "delay_ms": 10,
    "packet_loss_percent": 0,
}
TRAFFIC = {"protocol": "tcp", "duration_s": 5, "ping_count": 100, "ping_flood": True, "reverse": True}


def _path_node(base_scenario: dict, node_id: str) -> dict:
    node = next(node for node in base_scenario["nodes"] if node["id"] == node_id)
    return {
        key: deepcopy(value)
        for key, value in node.items()
        if key in {"id", "original_id", "original_label", "country", "latitude", "longitude"}
    }


def build_selected_path_scenario(base_scenario: dict, path_name: str) -> dict:
    if path_name not in PATHS:
        raise ValueError(f"Unknown Germany50 selected path: {path_name}")
    path = PATHS[path_name]
    source_links = base_scenario["links"]
    backbone_links = []
    for source, target in zip(path, path[1:]):
        original = find_link_between(source_links, source, target)
        backbone_links.append({"source": source, "target": target, "original_id": original.get("original_id"), **CONFIG})

    client_id = f"g50-{path_name}-client"
    server_id = f"g50-{path_name}-server"
    nodes = [{"id": client_id, "type": "client"}]
    nodes.extend({**_path_node(base_scenario, node_id), "type": "router"} for node_id in path)
    nodes.append({"id": server_id, "type": "server"})
    links = [
        {"source": client_id, "target": path[0], "role": "access-source", **CONFIG},
        *backbone_links,
        {"source": path[-1], "target": server_id, "role": "access-destination", **CONFIG},
    ]
    scenario = {
        "topology_name": f"sndlib-germany50-selected-{path_name}",
        "experiment_scope": "Germany50 path-extracted experiment; not a full 50-node run",
        "source_metadata": deepcopy(base_scenario["source_metadata"]),
        "addressing": deepcopy(base_scenario.get("addressing", {})),
        "nodes": nodes,
        "links": links,
        "traffic": {"source": client_id, "destination": server_id, **TRAFFIC},
        "experiment_metadata": {
            "path_class": path_name,
            "backbone_path": path,
            "backbone_hop_count": len(path) - 1,
            "path_definition": "fixed SNDlib Germany50 selected path",
        },
    }
    return validate_topology_scenario(scenario)


def write_selected_path_scenarios(base_scenario: dict, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for path_name in PATHS:
        scenario = build_selected_path_scenario(base_scenario, path_name)
        output_path = output_dir / f"germany50-{path_name}.json"
        import json
        output_path.write_text(json.dumps(scenario, indent=2) + "\n", encoding="utf-8")
        paths[path_name] = output_path
    return paths
