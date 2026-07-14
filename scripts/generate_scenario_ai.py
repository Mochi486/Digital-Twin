#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from ai_scenario_utils import (
    DEFAULT_OPENAI_MODEL,
    DEFAULT_PROVIDER,
    OPENAI_SYSTEM_PROMPT,
    build_openai_text_format,
    default_topology_name,
    extract_json_object,
    mock_generate_abstract_scenario,
    validate_and_project_generated_scenario,
)
from topology_utils import build_topology_svg


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNS_ROOT = PROJECT_ROOT / "runs" / "current"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--provider", choices=["mock", "openai"], default=DEFAULT_PROVIDER)
    parser.add_argument("--model", default=DEFAULT_OPENAI_MODEL)
    parser.add_argument("--topology-name", default="")
    parser.add_argument("--output-scenario", type=Path, default=RUNS_ROOT / "ai_scenario.json")
    parser.add_argument("--report", type=Path, default=RUNS_ROOT / "ai_scenario_report.json")
    parser.add_argument("--dry-run-output", type=Path, default=RUNS_ROOT / "ai_scenario_dry_run.json")
    parser.add_argument("--plot", type=Path, default=RUNS_ROOT / "ai_scenario.svg")
    parser.add_argument("--skip-dry-run", action="store_true")
    return parser.parse_args()


def openai_generate_abstract_scenario(prompt: str, model: str) -> tuple[dict | None, dict]:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None, {
            "status": "skipped_missing_api_key",
            "error": "OPENAI_API_KEY is not set.",
        }

    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": OPENAI_SYSTEM_PROMPT}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            },
        ],
        "text": {
            "format": build_openai_text_format(),
        },
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw_text = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_text = exc.read().decode("utf-8", errors="replace")
        return None, {
            "status": "http_error",
            "error": f"HTTP {exc.code}",
            "raw_response": error_text,
        }
    except OSError as exc:
        return None, {
            "status": "request_failed",
            "error": str(exc),
        }

    raw_payload = json.loads(raw_text)
    candidate = None
    if isinstance(raw_payload.get("output_text"), str) and raw_payload["output_text"].strip():
        candidate = extract_json_object(raw_payload["output_text"])
    else:
        for item in raw_payload.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    candidate = extract_json_object(content["text"])
                    break
            if candidate is not None:
                break
    if candidate is None:
        return None, {
            "status": "parse_error",
            "error": "Could not extract structured JSON from OpenAI response.",
            "raw_response": raw_payload,
        }
    return candidate, {
        "status": "ok",
        "response_id": raw_payload.get("id"),
        "raw_response": raw_payload,
    }


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

    if args.provider == "mock":
        candidate, raw_response = mock_generate_abstract_scenario(args.prompt)
        provider_result = {
            "status": "ok",
            "raw_response": raw_response,
        }
    else:
        candidate, provider_result = openai_generate_abstract_scenario(args.prompt, args.model)

    report = {
        "timestamp": timestamp,
        "prompt": args.prompt,
        "provider": args.provider,
        "model": args.model,
        "topology_name": topology_name,
        "provider_result": provider_result,
        "validation_result": None,
        "final_scenario": None,
        "dry_run": None,
    }

    if candidate is not None:
        validation_result = validate_and_project_generated_scenario(
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

    if report["provider_result"]["status"] == "skipped_missing_api_key":
        print(json.dumps({"status": "skipped_missing_api_key", "report": str(args.report)}, indent=2))
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
