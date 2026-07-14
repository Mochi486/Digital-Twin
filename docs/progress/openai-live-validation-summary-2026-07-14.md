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
- Expanded unit coverage to `36/36` passing tests.
- Revalidated the generic two-router real smoke path with the non-root prepare fallback.

## Mock Versus Live

- Mock AI scenarios remain completed:
  - generated
  - validated
  - dry-run validated
  - real WSL Docker validated
- OpenAI live scenario remains blocked:
  - request reached OpenAI
  - authentication failed before any scenario was accepted
  - no live dry-run or live Docker run was counted as complete

## Real OpenAI Attempt

- Request date: 2026-07-14
- Provider: `openai`
- SDK: `openai 2.45.0`
- Requested model: `gpt-5.6`
- Prompt:

```text
Create a connected six-node routed network topology with one client,
one server, four routers, two alternative paths, 20 Mbps bandwidth,
10 ms one-way delay, 0 percent packet loss, and one TCP traffic flow
from the client to the server.
```

- Evidence directory:
  - `D:\home\fanys23\project_70\.local-evidence\openai-live-validation-win-20260714-104540`
- Report file:
  - `D:\home\fanys23\project_70\.local-evidence\openai-live-validation-win-20260714-104540\openai-live-report.json`

## Result

- Error type: `AuthenticationError`
- HTTP status: `401`
- OpenAI error code: `invalid_api_key`
- Observed failure mode:
  - the current PowerShell `OPENAI_API_KEY` appears to contain a URL-like string ending in `/v1`
  - that is not a usable OpenAI API key

Because authentication failed:

- no response id was produced
- no token usage was produced
- no raw structured JSON response was produced
- no schema validation ran on a live candidate
- no semantic validation ran on a live candidate
- no deterministic scenario projection was accepted
- no simulator dry-run was accepted
- no real Docker run was started for the live scenario

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
- Real live scenario evidence: blocked by invalid key
- Germany50 / DFN full topology: still deferred by scope
- Optional RL: not started
- Paper analysis and writing: still pending

## Minimal Manual Action

1. Replace the current PowerShell `OPENAI_API_KEY` with a real OpenAI API key.
2. Rerun the live request.
3. If authentication succeeds, continue immediately with live dry-run and real Docker validation.
