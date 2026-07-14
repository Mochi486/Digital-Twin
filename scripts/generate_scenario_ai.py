#!/usr/bin/env python3
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from ai_scenario_utils import (
    DEFAULT_OPENAI_MODEL,
    DEFAULT_PROVIDER,
    OPENAI_SYSTEM_PROMPT,
    build_validation_gate_report,
    default_topology_name,
    mock_generate_abstract_scenario,
)
from openai_live_utils import create_provider_client, request_structured_scenario, resolve_provider_model
from topology_utils import build_topology_svg


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNS_ROOT = PROJECT_ROOT / "runs" / "current"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--provider", choices=["mock", "openai", "openai_compatible"], default=DEFAULT_PROVIDER)
    parser.add_argument("--model", default="")
    parser.add_argument(
        "--endpoint-type",
        choices=["responses_json_schema", "chat_json_schema", "chat_json_object", "chat_plain_json"],
        default="responses_json_schema",
    )
    parser.add_argument("--topology-name", default="")
    parser.add_argument("--output-scenario", type=Path, default=RUNS_ROOT / "ai_scenario.json")
    parser.add_argument("--report", type=Path, default=RUNS_ROOT / "ai_scenario_report.json")
    parser.add_argument("--dry-run-output", type=Path, default=RUNS_ROOT / "ai_scenario_dry_run.json")
    parser.add_argument("--plot", type=Path, default=RUNS_ROOT / "ai_scenario.svg")
    parser.add_argument("--skip-dry-run", action="store_true")
    return parser.parse_args()


def openai_generate_abstract_scenario(
    provider: str,
    prompt: str,
    model: str,
    endpoint_type: str,
    api_key_override: str | None = None,
) -> tuple[dict | None, dict]:
    client, sdk_status = create_provider_client(provider, api_key_override=api_key_override)
    if client is None:
        return None, {
            "status": "client_unavailable",
            "sdk_status": sdk_status,
            "error_type": sdk_status.get("error_type"),
            "error": sdk_status.get("error_message"),
        }

    response = request_structured_scenario(client, prompt, model, OPENAI_SYSTEM_PROMPT, endpoint_type)
    response["sdk_status"] = sdk_status
    if response["status"] != "ok":
        return None, response
    return response["structured_output"], response


def run_dry_run(output_path: Path, scenario: dict, plot_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    build_topology_svg(scenario, plot_path)
    dry_run = {
        "topology": scenario["topology_name"],
        "node_count": len(scenario["nodes"]),
        "link_count": len(scenario["links"]),
        "route_count": len(scenario["routes"]),
        "subnet_count": len(scenario["subnets"]),
        "plot_file": str(plot_path),
    }
    output_path.write_text(json.dumps(dry_run, indent=2) + "\n", encoding="utf-8")
    return dry_run


def main() -> int:
    args = parse_args()
    topology_name = args.topology_name or default_topology_name(args.prompt)
    timestamp = datetime.now().isoformat()
    model = resolve_provider_model(args.provider, args.model or DEFAULT_OPENAI_MODEL)

    if args.provider == "mock":
        candidate, raw_response = mock_generate_abstract_scenario(args.prompt)
        provider_result = {
            "status": "ok",
            "raw_response": raw_response,
        }
    else:
        candidate, provider_result = openai_generate_abstract_scenario(
            args.provider,
            args.prompt,
            model,
            args.endpoint_type,
        )

    report = {
        "timestamp": timestamp,
        "prompt": args.prompt,
        "provider": args.provider,
        "model": model,
        "endpoint_type": args.endpoint_type if args.provider != "mock" else None,
        "topology_name": topology_name,
        "provider_result": provider_result,
        "validation_result": None,
        "final_scenario": None,
        "dry_run": None,
    }

    if candidate is not None:
        validation_result = build_validation_gate_report(
            candidate,
            args.prompt,
            topology_name=topology_name,
        )
        report["validation_result"] = {
            key: value
            for key, value in validation_result.items()
            if key != "projected_scenario"
        }
        if validation_result["valid"]:
            scenario = validation_result["projected_scenario"]
            report["final_scenario"] = scenario
            args.output_scenario.parent.mkdir(parents=True, exist_ok=True)
            args.output_scenario.write_text(json.dumps(scenario, indent=2) + "\n", encoding="utf-8")
            if not args.skip_dry_run:
                report["dry_run"] = run_dry_run(args.dry_run_output, scenario, args.plot)
        else:
            provider_status = report["provider_result"].get("status")
            if provider_status == "ok":
                report["provider_result"]["status"] = "rejected_after_validation"

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if report["provider_result"]["status"] == "client_unavailable":
        print(json.dumps({"status": "client_unavailable", "report": str(args.report)}, indent=2))
        return 0

    if report["validation_result"] and report["validation_result"]["valid"]:
        print(
            json.dumps(
                {
                    "status": "ok",
                    "scenario": str(args.output_scenario),
                    "report": str(args.report),
                    "dry_run": str(args.dry_run_output) if report["dry_run"] else None,
                },
                indent=2,
            )
        )
        return 0

    print(json.dumps({"status": "rejected", "report": str(args.report)}, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
