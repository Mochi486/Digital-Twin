import ipaddress
import json
import math
import re
from collections import deque
from pathlib import Path

from routed_delay_utils import (
    build_bandwidth_qdisc_command,
    build_netem_qdisc_command,
    parse_ping_output,
    parse_throughput,
    summarize_numeric,
    theoretical_round_trip_loss_percent,
)


DEFAULT_ADDRESSING = {
    "base_cidr": "10.64.0.0/16",
    "subnet_prefixlen": 29,
}


def _coerce_token(token: str):
    if token.startswith('"') and token.endswith('"'):
        return token[1:-1]
    if re.fullmatch(r"-?\d+", token):
        return int(token)
    if re.fullmatch(r"-?\d+\.\d+", token):
        return float(token)
    return token


def _tokenize_gml(text: str) -> list[str]:
    return re.findall(r'"[^"\\]*(?:\\.[^"\\]*)*"|\[|\]|[^\s\[\]]+', text)


def _append_gml_value(container: dict, key: str, value):
    if key not in container:
        container[key] = value
    elif isinstance(container[key], list):
        container[key].append(value)
    else:
        container[key] = [container[key], value]


def _parse_gml_block(tokens: list[str], index: int) -> tuple[dict, int]:
    block = {}
    while index < len(tokens):
        token = tokens[index]
        if token == "]":
            return block, index + 1
        key = token
        index += 1
        value_token = tokens[index]
        if value_token == "[":
            value, index = _parse_gml_block(tokens, index + 1)
        else:
            value = _coerce_token(value_token)
            index += 1
        _append_gml_value(block, key, value)
    raise ValueError("Unterminated GML block.")


def parse_gml(path: Path) -> dict:
    tokens = _tokenize_gml(path.read_text(encoding="utf-8", errors="ignore"))
    parsed = {}
    index = 0
    while index < len(tokens):
        key = tokens[index]
        index += 1
        if index >= len(tokens):
            raise ValueError("Unexpected end of GML stream.")
        if tokens[index] == "[":
            value, index = _parse_gml_block(tokens, index + 1)
        else:
            value = _coerce_token(tokens[index])
            index += 1
        _append_gml_value(parsed, key, value)
    return parsed


def ensure_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def slugify_node_id(label: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", label.strip()).strip("-").lower()
    return slug or "node"


def build_graph_adjacency(node_ids: list[str], links: list[dict]) -> dict[str, set[str]]:
    adjacency = {node_id: set() for node_id in node_ids}
    for link in links:
        adjacency[link["source"]].add(link["target"])
        adjacency[link["target"]].add(link["source"])
    return adjacency


def shortest_path(adjacency: dict[str, set[str]], source: str, target: str) -> list[str]:
    if source == target:
        return [source]
    queue = deque([[source]])
    seen = {source}
    while queue:
        path = queue.popleft()
        for neighbor in sorted(adjacency[path[-1]]):
            if neighbor in seen:
                continue
            next_path = path + [neighbor]
            if neighbor == target:
                return next_path
            seen.add(neighbor)
            queue.append(next_path)
    raise ValueError(f"No path between {source} and {target}")


def all_pairs_shortest_paths(adjacency: dict[str, set[str]]) -> dict[tuple[str, str], list[str]]:
    pairs = {}
    node_ids = sorted(adjacency)
    for index, source in enumerate(node_ids):
        for target in node_ids[index + 1 :]:
            path = shortest_path(adjacency, source, target)
            pairs[(source, target)] = path
    return pairs


def ensure_connected(adjacency: dict[str, set[str]]):
    node_ids = list(adjacency)
    if not node_ids:
        raise ValueError("Topology must contain at least one node.")
    visited = set()
    queue = deque([node_ids[0]])
    while queue:
        node_id = queue.popleft()
        if node_id in visited:
            continue
        visited.add(node_id)
        queue.extend(sorted(adjacency[node_id] - visited))
    if visited != set(node_ids):
        missing = sorted(set(node_ids) - visited)
        raise ValueError(f"Topology is disconnected. Unreachable nodes: {', '.join(missing)}")


def infer_node_types(scenario: dict):
    traffic = scenario["traffic"]
    source_id = traffic["source"]
    destination_id = traffic["destination"]
    for node in scenario["nodes"]:
        if "type" in node:
            continue
        if node["id"] == source_id:
            node["type"] = "client"
        elif node["id"] == destination_id:
            node["type"] = "server"
        else:
            node["type"] = "router"


def validate_link_definitions(scenario: dict):
    node_ids = {node["id"] for node in scenario["nodes"]}
    link_pairs = set()
    for link in scenario["links"]:
        if link["source"] not in node_ids or link["target"] not in node_ids:
            raise ValueError(f"Link references unknown nodes: {link}")
        key = tuple(sorted((link["source"], link["target"])))
        if key in link_pairs:
            raise ValueError(f"Duplicate link detected between {key[0]} and {key[1]}")
        link_pairs.add(key)
        delay_ms = float(link.get("delay_ms", 0))
        packet_loss_percent = float(link.get("packet_loss_percent", 0))
        if delay_ms < 0:
            raise ValueError("delay_ms must be non-negative.")
        if packet_loss_percent < 0 or packet_loss_percent > 100:
            raise ValueError("packet_loss_percent must be between 0 and 100.")
        if "bandwidth_mbps" in link and float(link["bandwidth_mbps"]) <= 0:
            raise ValueError("bandwidth_mbps must be positive when specified.")


def normalize_compact_scenario(scenario: dict) -> dict:
    if "subnets" in scenario and "routes" in scenario and all("interfaces" in node for node in scenario["nodes"]):
        return scenario

    infer_node_types(scenario)
    validate_link_definitions(scenario)
    node_ids = [node["id"] for node in scenario["nodes"]]
    adjacency = build_graph_adjacency(node_ids, scenario["links"])
    ensure_connected(adjacency)

    addressing = dict(DEFAULT_ADDRESSING)
    addressing.update(scenario.get("addressing", {}))
    network_pool = ipaddress.ip_network(addressing["base_cidr"])
    subnet_prefixlen = int(addressing["subnet_prefixlen"])
    if subnet_prefixlen <= network_pool.prefixlen:
        raise ValueError("subnet_prefixlen must be larger than the base network prefix.")
    available_subnets = network_pool.subnets(new_prefix=subnet_prefixlen)

    nodes_by_id = {node["id"]: {**node, "interfaces": []} for node in scenario["nodes"]}
    normalized_subnets = []
    link_endpoints = {}

    for link_index, link in enumerate(scenario["links"], start=1):
        subnet = next(available_subnets, None)
        if subnet is None:
            raise ValueError("Address pool exhausted while allocating point-to-point subnets.")
        subnet_name = link.get("subnet", f"net_{link_index:03d}_{link['source']}_{link['target']}")
        hosts = list(subnet.hosts())
        if len(hosts) < 3:
            raise ValueError(
                f"Subnet {subnet} does not provide Docker gateway plus two usable endpoint addresses."
            )
        # Docker bridge reserves the first usable address as the gateway.
        source_ip = str(hosts[1])
        target_ip = str(hosts[2])
        normalized_subnets.append({"name": subnet_name, "cidr": str(subnet)})
        nodes_by_id[link["source"]]["interfaces"].append({"subnet": subnet_name, "ip": source_ip})
        nodes_by_id[link["target"]]["interfaces"].append({"subnet": subnet_name, "ip": target_ip})
        link["subnet"] = subnet_name
        link_endpoints[subnet_name] = {
            "cidr": str(subnet),
            "source": link["source"],
            "target": link["target"],
            "source_ip": source_ip,
            "target_ip": target_ip,
        }

    normalized_routes = generate_static_routes(
        list(nodes_by_id.values()),
        scenario["links"],
        normalized_subnets,
        adjacency,
        link_endpoints,
        mode=scenario.get("route_generation_mode", "all_subnets"),
        traffic=scenario.get("traffic", {}),
    )

    scenario["nodes"] = list(nodes_by_id.values())
    scenario["subnets"] = normalized_subnets
    scenario["routes"] = normalized_routes
    scenario["generated_routes"] = True
    scenario["resource_estimate"] = build_resource_estimate(scenario)
    return scenario


def generate_static_routes(
    nodes: list[dict],
    links: list[dict],
    subnets: list[dict],
    adjacency: dict[str, set[str]],
    link_endpoints: dict[str, dict],
    mode: str = "all_subnets",
    traffic: dict | None = None,
) -> list[dict]:
    subnets_by_name = {subnet["name"]: subnet for subnet in subnets}
    node_ids = [node["id"] for node in nodes]
    routes = []
    seen_destinations = {}
    traffic = traffic or {}

    if mode == "all_subnets":
        target_subnet_names = list(link_endpoints)
    elif mode == "traffic_endpoint_subnets":
        endpoint_nodes = [traffic["source"], traffic["destination"]]
        target_subnet_names = []
        for endpoint_node in endpoint_nodes:
            endpoint = get_node({"nodes": nodes}, endpoint_node)
            target_subnet_names.extend(iface["subnet"] for iface in endpoint["interfaces"])
        target_subnet_names = sorted(set(target_subnet_names))
    else:
        raise ValueError(f"Unsupported route_generation_mode: {mode}")

    for node_id in node_ids:
        attached_subnets = {iface["subnet"] for iface in get_node({"nodes": nodes}, node_id)["interfaces"]}
        for subnet_name in target_subnet_names:
            if subnet_name in attached_subnets:
                continue
            endpoint_info = link_endpoints[subnet_name]
            endpoints = [endpoint_info["source"], endpoint_info["target"]]
            candidate_paths = []
            for endpoint_node in endpoints:
                try:
                    candidate_paths.append(shortest_path(adjacency, node_id, endpoint_node))
                except ValueError:
                    continue
            if not candidate_paths:
                raise ValueError(f"No route path from {node_id} to subnet {subnet_name}")
            chosen_path = min(candidate_paths, key=lambda path: (len(path), path))
            if len(chosen_path) < 2:
                raise ValueError(f"Invalid route path for {node_id} to subnet {subnet_name}")
            next_hop_node = chosen_path[1]
            connecting_link = find_link_between(links, node_id, next_hop_node)
            next_hop_iface = get_interface(get_node({"nodes": nodes}, next_hop_node), connecting_link["subnet"])
            route = {
                "node": node_id,
                "destination": subnets_by_name[subnet_name]["cidr"],
                "via": next_hop_iface["ip"],
                "path": chosen_path,
                "hop_count": len(chosen_path) - 1,
            }
            route_key = (route["node"], route["destination"])
            previous = seen_destinations.get(route_key)
            if previous and previous["via"] != route["via"]:
                raise ValueError(
                    f"Route conflict for {route['node']} destination {route['destination']}: "
                    f"{previous['via']} vs {route['via']}"
                )
            seen_destinations[route_key] = route
            routes.append(route)

    return routes


def validate_explicit_scenario(scenario: dict) -> None:
    required_top_level = ["topology_name", "nodes", "subnets", "links", "routes", "traffic"]
    for field in required_top_level:
        if field not in scenario:
            raise ValueError(f"Missing required scenario field: {field}")

    node_ids = {node["id"] for node in scenario["nodes"]}
    subnet_names = {subnet["name"] for subnet in scenario["subnets"]}
    interface_pairs = set()
    adjacency = build_graph_adjacency(list(node_ids), scenario["links"])
    ensure_connected(adjacency)

    for node in scenario["nodes"]:
        interfaces = node.get("interfaces", [])
        if not interfaces:
            raise ValueError(f"Node {node['id']} must declare at least one interface.")
        for iface in interfaces:
            subnet_name = iface["subnet"]
            if subnet_name not in subnet_names:
                raise ValueError(f"Node {node['id']} references unknown subnet {subnet_name}.")
            interface_key = (subnet_name, iface["ip"])
            if interface_key in interface_pairs:
                raise ValueError(f"Duplicate interface IP {iface['ip']} on subnet {subnet_name}.")
            interface_pairs.add(interface_key)

    validate_link_definitions(scenario)
    for link in scenario["links"]:
        if link["subnet"] not in subnet_names:
            raise ValueError(f"Link references unknown subnet: {link['subnet']}")

    for route in scenario["routes"]:
        if route["node"] not in node_ids:
            raise ValueError(f"Route references unknown node: {route['node']}")

    check_route_conflicts(scenario["routes"])
    traffic = scenario["traffic"]
    if traffic["source"] not in node_ids or traffic["destination"] not in node_ids:
        raise ValueError("Traffic source/destination must reference known nodes.")
    scenario["resource_estimate"] = build_resource_estimate(scenario)


def check_route_conflicts(routes: list[dict]):
    seen = {}
    for route in routes:
        key = (route["node"], route["destination"])
        if key in seen and seen[key] != route["via"]:
            raise ValueError(
                f"Route conflict for {route['node']} destination {route['destination']}: "
                f"{seen[key]} vs {route['via']}"
            )
        seen[key] = route["via"]


def validate_topology_scenario(scenario: dict) -> dict:
    if "subnets" not in scenario or "routes" not in scenario or not all("interfaces" in node for node in scenario["nodes"]):
        scenario = normalize_compact_scenario(scenario)
    validate_explicit_scenario(scenario)
    return scenario


def load_topology_scenario(path: Path) -> dict:
    scenario = json.loads(path.read_text(encoding="utf-8"))
    return validate_topology_scenario(scenario)


def import_topology_zoo_gml(
    path: Path,
    topology_name: str,
    source_url: str,
    addressing: dict | None = None,
) -> dict:
    parsed = parse_gml(path)
    graph = parsed.get("graph")
    if not graph:
        raise ValueError("GML file does not contain a top-level graph block.")

    nodes = []
    node_id_map = {}
    for node in ensure_list(graph.get("node")):
        label = str(node.get("label", node["id"]))
        node_id = slugify_node_id(label)
        suffix = 1
        base_id = node_id
        while node_id in node_id_map.values():
            suffix += 1
            node_id = f"{base_id}-{suffix}"
        node_id_map[node["id"]] = node_id
        nodes.append(
            {
                "id": node_id,
                "type": "router",
                "original_id": node["id"],
                "original_label": label,
                "country": node.get("Country"),
                "latitude": node.get("Latitude"),
                "longitude": node.get("Longitude"),
            }
        )

    links = []
    for edge in ensure_list(graph.get("edge")):
        links.append(
            {
                "source": node_id_map[edge["source"]],
                "target": node_id_map[edge["target"]],
                "delay_ms": 0,
                "packet_loss_percent": 0,
            }
        )

    sorted_nodes = sorted(node["id"] for node in nodes)
    scenario = {
        "topology_name": topology_name,
        "source_metadata": {
            "source_url": source_url,
            "original_file": str(path),
            "geo_location": graph.get("GeoLocation"),
            "network_label": graph.get("label"),
        },
        "addressing": addressing or dict(DEFAULT_ADDRESSING),
        "nodes": nodes,
        "links": links,
        "traffic": {
            "source": sorted_nodes[0],
            "destination": sorted_nodes[-1],
            "protocol": "tcp",
            "duration_s": 2,
            "ping_count": 3,
            "reverse": True,
        },
    }
    return validate_topology_scenario(scenario)


def get_node(scenario: dict, node_id: str) -> dict:
    for node in scenario["nodes"]:
        if node["id"] == node_id:
            return node
    raise ValueError(f"Node not found: {node_id}")


def get_subnet(scenario: dict, subnet_name: str) -> dict:
    for subnet in scenario["subnets"]:
        if subnet["name"] == subnet_name:
            return subnet
    raise ValueError(f"Subnet not found: {subnet_name}")


def get_interface(node: dict, subnet_name: str) -> dict:
    for iface in node.get("interfaces", []):
        if iface["subnet"] == subnet_name:
            return iface
    raise ValueError(f"Node {node['id']} has no interface on subnet {subnet_name}")


def get_primary_ip(node: dict) -> str:
    return node["interfaces"][0]["ip"]


def get_destination_ip(scenario: dict) -> str:
    traffic = scenario["traffic"]
    if "destination_ip" in traffic:
        return traffic["destination_ip"]
    return get_primary_ip(get_node(scenario, traffic["destination"]))


def get_router_nodes(scenario: dict) -> list[dict]:
    return [node for node in scenario["nodes"] if node["type"] == "router"]


def get_link_impairment_plan(scenario: dict) -> list[dict]:
    plan = []
    for link in scenario["links"]:
        delay_ms = float(link.get("delay_ms", 0))
        packet_loss_percent = float(link.get("packet_loss_percent", 0))
        if delay_ms == 0 and packet_loss_percent == 0:
            continue
        for node_id in (link["source"], link["target"]):
            node = get_node(scenario, node_id)
            if node["type"] != "router":
                continue
            iface = get_interface(node, link["subnet"])
            plan.append(
                {
                    "link": f"{link['source']}->{link['target']}",
                    "subnet": link["subnet"],
                    "node": node["id"],
                    "interface_ip": iface["ip"],
                    "delay_ms": delay_ms,
                    "packet_loss_percent": packet_loss_percent,
                    "direction": "egress",
                }
            )
    return plan


def get_bandwidth_plan(scenario: dict) -> list[dict]:
    plan = []
    traffic = scenario.get("traffic", {})
    if not traffic:
        return plan
    source_node = traffic["destination"] if traffic.get("reverse", False) else traffic["source"]
    destination_node = traffic["source"] if traffic.get("reverse", False) else traffic["destination"]
    adjacency = build_graph_adjacency([node["id"] for node in scenario["nodes"]], scenario["links"])
    path = shortest_path(adjacency, source_node, destination_node)
    for node_a, node_b in zip(path, path[1:]):
        link = find_link_between(scenario["links"], node_a, node_b)
        if "bandwidth_mbps" not in link:
            continue
        source = get_node(scenario, node_a)
        if source["type"] != "router":
            continue
        iface = get_interface(source, link["subnet"])
        plan.append(
            {
                "link": f"{node_a}->{node_b}",
                "subnet": link["subnet"],
                "node": source["id"],
                "interface_ip": iface["ip"],
                "bandwidth_mbps": float(link["bandwidth_mbps"]),
                "direction": "egress",
                "path": path,
            }
        )
    return plan


def find_link_between(links: list[dict], node_a: str, node_b: str) -> dict:
    for link in links:
        if {link["source"], link["target"]} == {node_a, node_b}:
            return link
    raise ValueError(f"No link between {node_a} and {node_b}")


def build_route_command(route: dict) -> list[str]:
    return ["ip", "route", "add", route["destination"], "via", route["via"]]


def build_topology_svg(scenario: dict, output_path: Path) -> Path:
    nodes = scenario["nodes"]
    width = max(900, 180 * len(nodes))
    height = 320
    radius = 24
    cols = max(1, math.ceil(math.sqrt(len(nodes))))
    spacing_x = width / (cols + 1)
    rows = math.ceil(len(nodes) / cols)
    spacing_y = 180 / max(rows, 1)

    node_positions = {}
    node_elements = []
    label_elements = []
    for index, node in enumerate(nodes):
        col = index % cols
        row = index // cols
        x = spacing_x * (col + 1)
        y = 90 + spacing_y * row
        node_positions[node["id"]] = (x, y)
        fill = "#dfe9f3" if node["type"] == "router" else "#f8f4d7"
        node_elements.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{fill}" stroke="#1f2933" stroke-width="2"/>'
        )
        label_elements.append(
            f'<text x="{x:.1f}" y="{y + 4:.1f}" text-anchor="middle" font-size="11">{node["id"]}</text>'
        )

    line_elements = []
    for link in scenario["links"]:
        source_x, source_y = node_positions[link["source"]]
        target_x, target_y = node_positions[link["target"]]
        line_elements.append(
            f'<line x1="{source_x:.1f}" y1="{source_y:.1f}" '
            f'x2="{target_x:.1f}" y2="{target_y:.1f}" stroke="#1f2933" stroke-width="1.5"/>'
        )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
  <rect width="100%" height="100%" fill="white"/>
  <text x="{width / 2:.1f}" y="26" text-anchor="middle" font-size="20">{scenario['topology_name']}</text>
  {''.join(line_elements)}
  {''.join(node_elements)}
  {''.join(label_elements)}
</svg>
"""
    output_path.write_text(svg, encoding="utf-8")
    return output_path


def build_resource_estimate(scenario: dict) -> dict:
    return {
        "node_count": len(scenario["nodes"]),
        "router_count": len(get_router_nodes(scenario)),
        "link_count": len(scenario["links"]),
        "network_count": len(scenario["subnets"]),
        "route_count": len(scenario["routes"]),
        "impairment_applications": len(get_link_impairment_plan(scenario)),
        "bandwidth_controls": len(get_bandwidth_plan(scenario)),
    }


def select_connected_subset(scenario: dict, size: int, seed_node: str | None = None) -> dict:
    if size > len(scenario["nodes"]):
        raise ValueError("Subset size exceeds node count.")
    adjacency = build_graph_adjacency([node["id"] for node in scenario["nodes"]], scenario["links"])
    start = seed_node or sorted(adjacency)[0]
    visited = []
    queue = deque([start])
    seen = set()
    while queue and len(visited) < size:
        node_id = queue.popleft()
        if node_id in seen:
            continue
        seen.add(node_id)
        visited.append(node_id)
        queue.extend(sorted(adjacency[node_id] - seen))
    if len(visited) < size:
        raise ValueError(f"Could not build connected subset of size {size}.")

    subset_nodes = [get_node(scenario, node_id) for node_id in visited]
    subset_links = [
        link for link in scenario["links"] if link["source"] in seen and link["target"] in seen
    ]
    subset = {
        "topology_name": f"{scenario['topology_name']}-subset-{size}",
        "source_metadata": scenario.get("source_metadata", {}),
        "addressing": scenario.get("addressing", dict(DEFAULT_ADDRESSING)),
        "nodes": [
            {key: value for key, value in node.items() if key in {"id", "type", "original_id", "original_label", "country", "latitude", "longitude"}}
            for node in subset_nodes
        ],
        "links": [
            {
                key: value
                for key, value in link.items()
                if key in {"source", "target", "delay_ms", "packet_loss_percent", "bandwidth_mbps"}
            }
            for link in subset_links
        ],
        "traffic": {
            "source": visited[0],
            "destination": visited[-1],
            "protocol": "tcp",
            "duration_s": 2,
            "ping_count": 3,
            "reverse": True,
        },
    }
    return validate_topology_scenario(subset)


def choose_path_length_samples(scenario: dict) -> dict:
    adjacency = build_graph_adjacency([node["id"] for node in scenario["nodes"]], scenario["links"])
    pair_paths = all_pairs_shortest_paths(adjacency)
    ranked = sorted(pair_paths.items(), key=lambda item: (len(item[1]), item[0]))
    if not ranked:
        raise ValueError("No path samples available.")
    median_item = ranked[len(ranked) // 2]
    return {
        "shortest": {
            "pair": ranked[0][0],
            "path": ranked[0][1],
            "hop_count": len(ranked[0][1]) - 1,
        },
        "median": {
            "pair": median_item[0],
            "path": median_item[1],
            "hop_count": len(median_item[1]) - 1,
        },
        "longest": {
            "pair": ranked[-1][0],
            "path": ranked[-1][1],
            "hop_count": len(ranked[-1][1]) - 1,
        },
    }


__all__ = [
    "build_bandwidth_qdisc_command",
    "build_graph_adjacency",
    "build_netem_qdisc_command",
    "build_resource_estimate",
    "build_route_command",
    "build_topology_svg",
    "choose_path_length_samples",
    "ensure_connected",
    "find_link_between",
    "generate_static_routes",
    "get_bandwidth_plan",
    "get_destination_ip",
    "get_interface",
    "get_link_impairment_plan",
    "get_node",
    "get_primary_ip",
    "get_router_nodes",
    "get_subnet",
    "import_topology_zoo_gml",
    "load_topology_scenario",
    "parse_gml",
    "parse_ping_output",
    "parse_throughput",
    "select_connected_subset",
    "shortest_path",
    "summarize_numeric",
    "theoretical_round_trip_loss_percent",
    "validate_topology_scenario",
]
