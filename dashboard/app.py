"""Lightweight Streamlit UI for existing Digital Twin APIs and tracked evidence."""
import json
import subprocess
import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from ai_scenario_utils import build_validation_gate_report, mock_generate_abstract_scenario  # noqa: E402
from generate_scenario_ai import run_dry_run  # noqa: E402
from topology_utils import build_topology_svg, load_topology_scenario  # noqa: E402

CURRENT = PROJECT_ROOT / "runs" / "current"
GERMANY50_SUMMARY = PROJECT_ROOT / "runs" / "germany50-selected-paths-final" / "summary.json"
RL_SUMMARY = PROJECT_ROOT / "runs" / "minimal-rl-path-control-v1" / "summary.json"


def read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"error": str(exc), "path": str(path)}


def scenario_choices() -> list[Path]:
    return sorted(path for path in (PROJECT_ROOT / "data").rglob("*.json") if path.is_file())


def show_json_file(label: str, path: Path):
    value = read_json(path)
    if value is None:
        st.info(f"{label}: artifact not present yet — {path.relative_to(PROJECT_ROOT)}")
    else:
        st.caption(f"{label}: {path.relative_to(PROJECT_ROOT)}")
        st.json(value)


def render_experiment_results():
    st.subheader("Representative experiment results")
    germany = read_json(GERMANY50_SUMMARY)
    if germany:
        st.markdown("**Germany50 selected paths** — path-extracted experiment, not a full 50-node run.")
        st.dataframe(germany.get("summaries", []), use_container_width=True)
        st.image(str(GERMANY50_SUMMARY.parent / "hop-count-vs-rtt.svg"), caption="Germany50 path hops vs RTT")
    else:
        st.info("Germany50 selected-path summary is not available.")
    rl = read_json(RL_SUMMARY)
    if rl:
        st.markdown("**Minimal RL dual-path evaluation** — six nodes, two static paths.")
        st.json({key: rl.get(key) for key in ("episodes", "selected_path_counts", "q_learning", "baselines", "route_switch_verification")})
        for name in ("reward.svg", "path-selection.svg", "rtt.svg", "throughput.svg"):
            image = RL_SUMMARY.parent / name
            if image.exists():
                st.image(str(image), caption=name)
    else:
        st.info("RL results will appear after `scripts/minimal_rl_path_control.py --docker` completes.")


def scenario_panel():
    st.subheader("Scenario selection, validation, and dry-run")
    choices = scenario_choices()
    selected = st.selectbox("Existing JSON scenario", choices, format_func=lambda path: str(path.relative_to(PROJECT_ROOT)))
    if selected:
        try:
            scenario = load_topology_scenario(selected)
            st.success(f"Schema/route validation passed: {len(scenario['nodes'])} nodes, {len(scenario['links'])} links.")
            st.json(scenario)
            preview = CURRENT / "dashboard-selected-topology.svg"
            preview.parent.mkdir(parents=True, exist_ok=True)
            build_topology_svg(scenario, preview)
            st.image(str(preview), caption="Topology preview")
        except Exception as exc:  # UI surfaces validation errors instead of hiding them.
            st.error(f"Scenario validation failed: {exc}")
    st.caption("Optional real run uses the existing generic simulator; it never stores API keys.")
    if st.button("Optional real Run", type="secondary"):
        output, plot = CURRENT / "dashboard-metrics.json", CURRENT / "dashboard-topology.svg"
        command = [sys.executable, str(SCRIPTS_DIR / "simulator_topology.py"), "--scenario", str(selected), "--output", str(output), "--plot", str(plot)]
        with st.spinner("Running the existing simulator..."):
            completed = subprocess.run(command, capture_output=True, text=True, timeout=180)
        if completed.returncode == 0:
            st.success("Real run completed.")
            show_json_file("Metrics", output)
        else:
            st.error("Real run failed; see sanitized command output below.")
            st.code((completed.stderr or completed.stdout)[-4000:])


def ai_panel():
    st.subheader("AI scenario prompt")
    prompt = st.text_area("Prompt", "Create a six-node redundant routed topology with two candidate paths and 20 Mbps bandwidth")
    st.caption("Generate/Validate/Dry-run use the existing guarded mock provider by default. API keys are only read from environment variables and are never displayed or saved.")
    if st.button("Generate, Validate, Dry-run", type="primary"):
        candidate, raw = mock_generate_abstract_scenario(prompt)
        gate = build_validation_gate_report(candidate, prompt)
        st.json({"generated_candidate": candidate, "provider_response": raw, "validation": {key: value for key, value in gate.items() if key != "projected_scenario"}})
        if gate["valid"]:
            scenario = gate["projected_scenario"]
            scenario_path, report_path, dry_path, plot_path = (CURRENT / "dashboard-ai-scenario.json", CURRENT / "dashboard-ai-report.json", CURRENT / "dashboard-ai-dry-run.json", CURRENT / "dashboard-ai-topology.svg")
            CURRENT.mkdir(parents=True, exist_ok=True)
            scenario_path.write_text(json.dumps(scenario, indent=2) + "\n", encoding="utf-8")
            dry_run = run_dry_run(dry_path, scenario, plot_path)
            report_path.write_text(json.dumps({"prompt": prompt, "validation": gate["valid"], "dry_run": dry_run}, indent=2) + "\n", encoding="utf-8")
            st.success("Generated scenario passed validation and dry-run.")
            st.image(str(plot_path), caption="Generated topology")
            st.caption(f"Metrics/artifact location: {scenario_path.relative_to(PROJECT_ROOT)}")
        else:
            st.error("Generated scenario was rejected by validation; no real run was started.")


def main():
    st.set_page_config(page_title="Digital Twin Dashboard", layout="wide")
    st.title("Digital Twin — bounded experiment dashboard")
    st.caption("Core baseline: core-platform-v1. This UI reuses Python APIs; it does not duplicate simulator logic.")
    st.sidebar.caption("API keys: environment variables only; key values are never read into the page or displayed.")
    page = st.sidebar.radio("View", ["Results", "Scenario", "AI scenario"])
    if page == "Results":
        render_experiment_results()
    elif page == "Scenario":
        scenario_panel()
    else:
        ai_panel()


if __name__ == "__main__":
    main()
