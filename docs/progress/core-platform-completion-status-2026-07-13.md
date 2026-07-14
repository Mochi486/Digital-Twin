# Core Platform Completion Status

Date: 2026-07-13

## Completed Core Platform

- WSL Docker execution path verified with `docker version`, `docker info`, and `hello-world`
- Experiment image path stabilized around `Dockerfile.iperf` and `my-iperf-tc`
- Single-router routed simulator available
- Generic multi-hop topology simulator available
- Deterministic compact-topology normalization available
- Deterministic subnet allocation available
- Deterministic static-route generation available
- Route verification and route-table capture available
- Per-link delay, loss, and bandwidth control available
- Metrics persistence with timings, qdisc state, route tables, and resource estimates available
- Prompt-driven AI scenario generation available
- Mock provider available
- Official OpenAI provider with Responses API Structured Outputs integration available
- Third-party OpenAI-compatible provider available with live bounded validation, endpoint fallback, and synchronized WSL host-routing preparation
- Safety gates for schema, semantic, and forbidden-content rejection available

## Completed Real Experiments

- Single-router routed real experiments from earlier phases
- Two-router real acceptance, delay regression, and packet-loss regression from earlier phases
- AI `linear-5` real run `01`
- AI `linear-5` real run `02`
- AI `redundant-6` real run `01`
- AI `lossy-8` real run `01`
- Current-phase delay smoke regression
- Current-phase packet-loss smoke regression
- Third-party compatible-provider six-node live run on `2026-07-14`

## Completed But Dry-Run Only

- single-router compact dry-run in current AI phase
- two-router dry-run in current AI phase
- full DFN imported topology dry-run
- AI generator dry-runs for `linear-5`, `redundant-6`, and `lossy-8`

## Paused / Deferred

### Germany50 / DFN Full Topology

- Import support is complete.
- Dry-run support is complete.
- 5-node and 10-node subset smoke validation is complete.
- Full 58-node / 87-link traffic execution remains paused.
- Large-scale WSL forwarding work is intentionally deferred.

### Optional RL

- Not started.
- Still outside current scope.

## Paper-Phase Work Still Needed

- consolidate final experimental tables and comparisons
- produce cleaned figures for AI scenarios, delay, and packet-loss regressions
- interpret measured loss/RTT behavior against configured impairments
- write methodology, limitations, and threat-to-validity sections
- document why Germany50 / DFN full traffic was paused
- decide whether OpenAI live generation will be part of the paper artifact or only an optional extension

## Remaining Gap To Full Core Completion

One external blocker remains relative to the current bounded scope:

- restore official OpenAI API quota or billing so the official live provider path can complete schema validation, dry-run, and real Docker evidence

Everything else requested in the non-DFN, non-RL bounded scope is implemented and validated or explicitly paused by scope.
