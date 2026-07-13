import json
from pathlib import Path

from routed_delay_utils import (
    build_bandwidth_qdisc_command,
    build_netem_qdisc_command,
    parse_ping_output,
    parse_throughput,
    summarize_numeric,
    theoretical_round_trip_loss_percent,
)


def load_topology_scenario(path: Path) -> dict:
    scenario = json.loads(path.read_text(encoding="utf-8"))
    validate_topology_scenario(scenario)
    return scenario


def validate_topology_scenario(scenario: dict) -> None:
    required_top_level = ["topology_name", "nodes", "subnets", "links", "routes", "traffic"]
    for field in required_top_level:
        if field not in scenario:
            raise ValueError(f"Missing required scenario field: {field}")

    node_ids = {node["id"] for node in scenario["nodes"]}
    subnet_names = {subnet["name"] for subnet in scenario["subnets"]}
    interface_pairs = set()

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

    for link in scenario["links"]:
        if link["source"] not in node_ids or link["target"] not in node_ids:
            raise ValueError(f"Link references unknown nodes: {link}")
        if link["subnet"] not in subnet_names:
            raise ValueError(f"Link references unknown subnet: {link['subnet']}")
        delay_ms = float(link.get("delay_ms", 0))
        packet_loss_percent = float(link.get("packet_loss_percent", 0))
        if delay_ms < 0:
            raise ValueError("delay_ms must be non-negative.")
        if packet_loss_percent < 0 or packet_loss_percent > 100:
            raise ValueError("packet_loss_percent must be between 0 and 100.")
        if "bandwidth_mbps" in link and float(link["bandwidth_mbps"]) <= 0:
            raise ValueError("bandwidth_mbps must be positive when specified.")

    for route in scenario["routes"]:
        if route["node"] not in node_ids:
            raise ValueError(f"Route references unknown node: {route['node']}")

    traffic = scenario["traffic"]
    if traffic["source"] not in node_ids or traffic["destination"] not in node_ids:
        raise ValueError("Traffic source/destination must reference known nodes.")


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
    for link in scenario["links"]:
        if "bandwidth_mbps" not in link:
            continue
        target_node = get_node(scenario, link["target"])
        iface = get_interface(target_node, link["subnet"])
        plan.append(
            {
                "link": f"{link['source']}->{link['target']}",
                "subnet": link["subnet"],
                "node": target_node["id"],
                "interface_ip": iface["ip"],
                "bandwidth_mbps": float(link["bandwidth_mbps"]),
            }
        )
    return plan


def build_route_command(route: dict) -> list[str]:
    return ["ip", "route", "add", route["destination"], "via", route["via"]]


def build_topology_svg(scenario: dict, output_path: Path) -> Path:
    nodes = scenario["nodes"]
    width = 900
    height = 260
    spacing = width / (len(nodes) + 1)
    y = 120
    radius = 30

    node_positions = {}
    node_elements = []
    label_elements = []
    for index, node in enumerate(nodes, start=1):
        x = spacing * index
        node_positions[node["id"]] = (x, y)
        fill = "#dfe9f3" if node["type"] == "router" else "#f8f4d7"
        node_elements.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{fill}" stroke="#1f2933" stroke-width="2"/>'
        )
        label_elements.append(
            f'<text x="{x:.1f}" y="{y + 6:.1f}" text-anchor="middle" font-size="14">{node["id"]}</text>'
        )
        iface_labels = ", ".join(iface["subnet"] for iface in node["interfaces"])
        label_elements.append(
            f'<text x="{x:.1f}" y="{y + 58:.1f}" text-anchor="middle" font-size="12">{iface_labels}</text>'
        )

    line_elements = []
    for link in scenario["links"]:
        source_x, source_y = node_positions[link["source"]]
        target_x, target_y = node_positions[link["target"]]
        line_elements.append(
            f'<line x1="{source_x + radius:.1f}" y1="{source_y:.1f}" '
            f'x2="{target_x - radius:.1f}" y2="{target_y:.1f}" stroke="#1f2933" stroke-width="2"/>'
        )
        mid_x = (source_x + target_x) / 2
        line_elements.append(
            f'<text x="{mid_x:.1f}" y="{source_y - 18:.1f}" text-anchor="middle" font-size="12">{link["subnet"]}</text>'
        )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
  <rect width="100%" height="100%" fill="white"/>
  <text x="{width / 2:.1f}" y="28" text-anchor="middle" font-size="20">{scenario['topology_name']}</text>
  {''.join(line_elements)}
  {''.join(node_elements)}
  {''.join(label_elements)}
</svg>
"""
    output_path.write_text(svg, encoding="utf-8")
    return output_path


__all__ = [
    "build_bandwidth_qdisc_command",
    "build_netem_qdisc_command",
    "build_route_command",
    "build_topology_svg",
    "get_bandwidth_plan",
    "get_destination_ip",
    "get_interface",
    "get_link_impairment_plan",
    "get_node",
    "get_primary_ip",
    "get_router_nodes",
    "get_subnet",
    "load_topology_scenario",
    "parse_ping_output",
    "parse_throughput",
    "summarize_numeric",
    "theoretical_round_trip_loss_percent",
    "validate_topology_scenario",
]
