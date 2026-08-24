# Dissertation Research Questions

## Working Title

**An Artifact-Supported Docker Network Digital Twin**

## Main Research Question

**Identifier:** RQ0

**Question:** How effectively can a Docker-based network digital twin enforce and measure controlled network conditions while retaining an artifact-supported, extensible workflow across increasingly complex topologies and automated control workflows?

**Evidence mapping:**

- Controlled impairment experiments: Phase B inventory entries for bandwidth, configured one-way latency versus measured RTT, and configured one-way packet loss versus measured end-to-end loss.
- Reproducible workflow: retained scenario files, per-run metrics, summaries, plots, reproduction scripts, validation checks, and cleanup evidence mapped in `notes/experiment_inventory.md`.
- Topology extension: direct and dual-router evidence; Germany50 extracted paths; full 50-node/88-link instantiation; full route-plan dry-run; selected representative real traffic.
- Automated workflows: validated AI scenario-generation paths and the 80-episode real-Docker control comparison.

**Evidence boundaries:**

- The 20-Mbps historical result is a single retained record and is not treated as a repeated-run cohort.
- Germany50's 4,224-entry route plan was dry-run validated; real traffic covered three representative paths, not all pairs.
- Official OpenAI returned HTTP 429; the successful result used a separate OpenAI-compatible Qwen path.
- The threshold heuristic achieved a higher mean reward than the evaluated Q-learning configuration; no universal RL superiority or inferiority claim is supported.
- Dashboard validation is `DOCUMENTED_ONLY` because raw UI-path validation logs are not retained.

**Planned sections:** Introduction; System Design and Methodology; Experimental Methodology; Results; Discussion.

**Status:** SUPPORTED_WITH_EXPLICIT_BOUNDARIES

## RQ1 — Controlled Network Conditions

**Question:** How closely and consistently do measured network behaviours follow configured bandwidth, latency, and packet-loss conditions across repeated experiments?

**Evidence mapping:**

- Bandwidth: historical 20-Mbps record and the separate repeated 50/100-Mbps direct-topology cohorts.
- Latency: five-run cohorts at each configured one-way delay condition, with measured end-to-end RTT statistics.
- Packet loss: five-run cohorts at each configured one-way loss condition, with measured end-to-end loss and packet totals.
- Cross-topology reference: the separate five-run dual-router 20-Mbps benchmark.
- Statistical provenance: `REPOSITORY_REPORTED` and `AUDIT_COMPUTED` values in `notes/experiment_inventory.md` and `derived/audit_computed_statistics/experiment_summary.json`.

**Evidence boundaries:**

- Configured one-way delay and measured RTT are different quantities.
- Configured one-way loss and measured end-to-end ping loss are different quantities.
- The single historical 20-Mbps record must not be presented as equivalent to a repeated cohort.
- Direct-topology bandwidth cohorts and the dual-router benchmark must remain separate.

**Planned sections:** Experimental Methodology; Results; Discussion.

**Status:** SUPPORTED

## RQ2 — Topology Extension and Routing

**Question:** How does the framework extend from simple Docker topologies to multi-router and larger network topologies while preserving validated routing and measurable real traffic?

**Evidence mapping:**

- Simple and multi-router execution: direct-topology validation and the dual-router benchmark.
- Controlled Germany50-derived scaling: shortest, median, and longest extracted-path experiments with route and qdisc verification.
- Full Germany50 topology: 50-node/88-link instantiation, selected-route provisioning, representative shortest/median/longest real traffic, and cleanup evidence.
- Full routing-plan validation: the separately retained 4,224-entry dry-run plan.

**Evidence boundaries:**

- The extracted-path experiments are not full 50-node deployments.
- The complete 4,224-entry plan was validated in dry-run mode only.
- Full-topology real traffic was limited to three representative endpoint pairs using selected on-demand routes.
- No all-pairs real-traffic or complete-route-installation claim is supported.

**Planned sections:** System Design and Methodology; Experimental Methodology; Results; Discussion.

**Status:** SUPPORTED_WITH_EXPLICIT_SCOPE_LIMIT

## RQ3 — AI-Assisted Generation and Closed-Loop Control

**Question:** Can validated AI-assisted scenario generation and closed-loop learning-based control operate on the same digital-twin execution environment, and what limitations emerge in doing so?

**Evidence mapping:**

- Scenario-generation validation: schema, semantic, prompt-constraint, projection, dry-run, and controlled-execution mechanisms.
- Provider evidence: sanitized official OpenAI HTTP 429 evidence and separate successful OpenAI-compatible Qwen validation.
- Closed-loop control: real-Docker Q-learning and threshold-heuristic episodes, per-episode measurements, route decisions, summaries, and plots.
- Aggregate RL evidence: 80 valid real-Docker episodes across four policies, with failed/retried attempts retained separately.
- Interface context: small-topology interactive Dashboard implementation; quantitative UI-path validation remains `DOCUMENTED_ONLY`.

**Evidence boundaries:**

- Qwen-compatible success is not official OpenAI success.
- Official OpenAI evidence records an unsuccessful HTTP 429 outcome.
- The threshold heuristic achieved a higher mean reward than the evaluated Q-learning configuration.
- The evidence supports a functioning learnable control loop, not optimality or RL superiority.
- The Dashboard is not a Germany50 management interface, RL training interface, or arbitrary Docker command runner.

**Planned sections:** System Design and Methodology; Results; Discussion.

**Status:** SUPPORTED_WITH_NEGATIVE_AND_LIMITATION_RESULTS

## Core Claim

Within the evaluated configurations, the proposed Docker-based network digital twin provides a reproducibility-oriented, artifact-supported workflow for controlled network impairment experiments, extends to larger network topologies with validated routing and representative real traffic, and supports validated AI-assisted scenario generation and real-Docker closed-loop control. The evaluation also identifies clear limitations in large-topology traffic coverage and learning-based control performance.

**Evidence mapping:** RQ1 impairment evidence; RQ2 topology and routing evidence; RQ3 AI and real-Docker control evidence; evidence provenance and limitations in `notes/experiment_inventory.md`.

**Status:** SUPPORTED_WITH_EXPLICIT_BOUNDARIES

## Primary Contributions

### C1 — Reproducible Scenario-Driven Docker NDT Framework

**Contribution:** A scenario-driven Docker network digital-twin framework with deterministic topology construction, routing validation, controlled impairments, measurement capture, scoped cleanup, and retained reproduction scripts.

**Evidence mapping:** Direct, routed, dual-router, Germany50, AI-validation, RL-control, raw metrics, summaries, scenario configurations, and reproduction-script entries in `notes/experiment_inventory.md`.

**Boundary:** Retained artifacts and repeated cohorts support later inspection and rerunning, but the missing dedicated fresh-clone report prevents a completed independent-replication claim.

**Status:** SUPPORTED_WITH_DOCUMENTED_REPRODUCIBILITY_LIMIT

### C2 — Quantitative Impairment and Topology-Scaling Evaluation

**Contribution:** A quantitative evaluation spanning controlled bandwidth, latency, packet loss, multi-router execution, Germany50-derived paths, and full-topology selected-route validation.

**Evidence mapping:** RQ1 and RQ2 inventory entries, including raw runs, summaries, existing plots, and audit-computed statistics.

**Boundary:** Germany50 performance claims apply to selected representative paths; the full route plan is dry-run evidence rather than all-pairs traffic evidence.

**Status:** SUPPORTED

### C3 — AI-Assisted Generation and Real-Docker Closed-Loop Control Evaluation

**Contribution:** An evaluation of validated AI-assisted scenario generation and real-Docker closed-loop control, including the observed underperformance of the tested Q-learning configuration relative to the threshold heuristic.

**Evidence mapping:** Official OpenAI 429 evidence, Qwen-compatible validation evidence, Q-learning and heuristic per-episode evidence, the 80-episode aggregate, summaries, and plots.

**Boundary:** Provider outcomes remain separate; the result supports Q-learning underperformance in the evaluated setting, not a general rejection of RL.

**Status:** SUPPORTED_WITH_NEGATIVE_RESULT

## Working Research Gap

Existing research establishes several strong but mostly separate foundations: NDT concepts and reference architectures; data-driven network-performance modeling; reproducible and container-based network emulation; realistic topology datasets and multi-site topology prototyping; AI-assisted network configuration; and digital-twin-assisted reinforcement learning for network optimization and resource management.

The working gap addressed by this dissertation is therefore not the absence of any one of those components. It is the need for an integrated and empirically evaluated workflow that brings them together in a scenario-driven Docker network digital twin with a common execution and evidence pipeline. Within a single bounded framework, the dissertation evaluates controlled bandwidth, latency, and packet-loss enforcement; extension from direct and multi-router scenarios to a larger Germany50 topology; validated AI-assisted scenario generation; and closed-loop real-Docker control against an explicit heuristic baseline.

This gap is deliberately scoped by the retained evidence:

- Germany50 contributes full-topology instantiation, dry-run validation of the complete route plan, and real traffic on three representative paths; it does not establish all-pairs real-traffic coverage.
- The official OpenAI attempt returned HTTP 429, while successful generation used a separate OpenAI-compatible Qwen path; the latter is not evidence of official OpenAI success.
- The evaluated threshold heuristic achieved a higher mean reward than the tested Q-learning configuration; the contribution is an evidence-backed closed-loop comparison, not a claim of RL superiority, inferiority, or optimality.
- Dashboard evidence concerns a small-topology interactive interface and is documented-only where raw validation logs are absent; it is not a Germany50 management or RL-training dashboard.

Accordingly, the dissertation does not claim to be the first Docker network emulator, the first NDT, the first AI networking system, or the first digital-twin-plus-RL system. Its contribution is the design and quantitative evaluation of their scoped integration, together with explicit evidence provenance and limitations.
