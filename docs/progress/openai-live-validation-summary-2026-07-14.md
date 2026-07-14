# OpenAI Live Validation Summary

Date: 2026-07-14

## Scope

- Validate the real OpenAI provider with the official Python SDK and Responses API Structured Outputs.
- Use the required six-node prompt.
- Preserve secret safety.
- Continue to real WSL Docker execution only if the live response passes every validation gate.

## What Was Completed

- Added `scripts/openai_live_utils.py` for:
  - official OpenAI SDK integration
  - strict JSON Schema Structured Outputs request formatting
  - safe redaction of credential-like strings in error payloads
  - model-list fallback helpers
- Updated `scripts/generate_scenario_ai.py` to:
  - prefer `OPENAI_MODEL` when present
  - use the official OpenAI Python SDK instead of manual `urllib`
  - persist live provider metadata in the report
  - reuse the shared validation-gate report
- Added `scripts/run_openai_live_validation.py` as a bounded live-validation runner.
- Updated `scripts/prepare_wsl_docker.py` so host `iptables` preparation can run either:
  - directly as root
  - or via a temporary privileged Docker helper that `chroot`s into the WSL host root filesystem
- Expanded unit coverage and later closure validation to `43/43` passing tests.
- Revalidated the generic two-router real smoke path with the non-root prepare fallback.

## Mock Versus Live

- Mock AI scenarios remain completed:
  - generated
  - validated
  - dry-run validated
  - real WSL Docker validated
- OpenAI live scenario remains blocked:
  - request reached OpenAI
  - authentication and schema issues were resolved far enough to expose the current quota blocker
  - no live dry-run or live Docker run was counted as complete

## Real OpenAI Attempts

- Attempt 1:
  - Request date: `2026-07-14`
  - Provider: `openai`
  - SDK: `openai 2.45.0`
  - Requested model: `gpt-5.6`
  - Result: `AuthenticationError` / HTTP `401` / `invalid_api_key`
  - Cause: the previous PowerShell `OPENAI_API_KEY` value was a URL-like string ending in `/v1`
- Attempt 2:
  - Request date: `2026-07-14`
  - Provider: `openai`
  - SDK: `openai 2.45.0`
  - Requested model: `gpt-5.6`
  - Result: `BadRequestError` / HTTP `400` / `invalid_json_schema`
  - Cause: OpenAI Structured Outputs rejected the earlier schema because object `required` lists were incomplete
- Attempt 3:
  - Request date: `2026-07-14`
  - Provider: `openai`
  - SDK: `openai 2.45.0`
  - Requested model: `gpt-5.6`
  - Result: `RateLimitError` / HTTP `429` / `insufficient_quota`
  - Cause: the account currently has insufficient quota or billing capacity

- Latest blocker attempt: `3`
- Prompt:

```text
Create a connected six-node routed network topology with one client,
one server, four routers, two alternative paths, 20 Mbps bandwidth,
10 ms one-way delay, 0 percent packet loss, and one TCP traffic flow
from the client to the server.
```

- Latest evidence directory:
  - `D:\home\fanys23\project_70\.local-evidence\openai-live-validation-20260714-030746`
- Latest report file:
  - `D:\home\fanys23\project_70\.local-evidence\openai-live-validation-20260714-030746\openai-live-summary.json`

## Result

- Latest error type: `RateLimitError`
- Latest HTTP status: `429`
- Latest OpenAI error code: `insufficient_quota`
- Observed latest failure mode:
  - the corrected PowerShell `OPENAI_API_KEY` is non-empty and non-URL
  - the request now clears authentication and schema checks far enough to fail on account quota
  - no model-access fallback was needed because the request did not fail on model authorization

Because quota failed before a response payload was created:

- no response id was produced
- no token usage was produced
- no raw structured JSON response was produced
- no schema validation ran on a live candidate
- no semantic validation ran on a live candidate
- no deterministic scenario projection was accepted
- no simulator dry-run was accepted
- no real Docker run was started for the live scenario

This file records only the official OpenAI API path. Third-party OpenAI-compatible provider work is tracked separately in `docs/progress/openai-compatible-live-validation-summary-2026-07-14.md`, where the bounded `qwen3.7-plus` live generation and real WSL Docker execution completed on `2026-07-14`.

## Lightweight Regressions Completed During Live Closure

- `43/43` unit tests passed
- single-router dry-run passed
- two-router dry-run passed
- one delay smoke real run passed
- one packet-loss smoke real run passed
- invalid-scenario rejection evidence regenerated

Regression evidence:

- `D:\home\fanys23\project_70\.local-evidence\openai-live-regressions-20260714-110941`

## Security Notes

- No API key value was printed.
- No API key value was written to `.env`, logs, metrics, or Git.
- Live error payloads were redacted before persistence.
- Evidence paths remain under `project_70\.local-evidence`.

## Current Platform Status

- Bounded live-provider code path: implemented
- Structured Outputs request path: implemented
- Validation-gate reporting: implemented
- Non-root WSL host-rule preparation fallback: implemented
- Real live scenario evidence: blocked by account quota
- Germany50 / DFN full topology: still deferred by scope
- Optional RL: not started
- Paper analysis and writing: still pending

## Minimal Manual Action

1. Restore available OpenAI API quota or billing for the current account.
2. Rerun `scripts/run_openai_live_validation.py`.
3. If quota clears, the same script will continue into validation, dry-run, and real Docker execution.
