#!/usr/bin/env python3
import json
from datetime import datetime

from run_ai_scenario_phase import (
    EVIDENCE_ROOT,
    run_single_router_dry_run,
    run_two_router_dry_run,
    run_routed_regression,
    validate_invalid_cases,
)


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    evidence_dir = EVIDENCE_ROOT / f"openai-live-regressions-{stamp}"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "evidence_dir": str(evidence_dir),
        "single_router_dry_run": run_single_router_dry_run(evidence_dir),
        "two_router_dry_run": run_two_router_dry_run(evidence_dir),
        "delay_smoke": run_routed_regression("delay-smoke", evidence_dir, delay_ms=30, packet_loss_percent=0),
        "packet_loss_smoke": run_routed_regression(
            "packet-loss-smoke",
            evidence_dir,
            delay_ms=0,
            packet_loss_percent=3,
            ping_count=50,
            ping_interval_s=0.05,
        ),
        "invalid_scenario_validation": validate_invalid_cases(evidence_dir),
    }
    summary_path = evidence_dir / "openai-live-regressions-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence_dir": str(evidence_dir), "summary_file": str(summary_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
