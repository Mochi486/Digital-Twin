# OpenAI-Compatible Live Validation Summary

Date: 2026-07-14

## Scope

- Validate the bounded third-party `openai_compatible` provider path without relabeling it as `openai`.
- Reuse the required six-node prompt.
- Probe models only after model-list discovery succeeds.
- Preserve secret safety and save only sanitized provider metadata.

## Implemented Provider Changes

- Extended provider handling to:
  - `mock`
  - `openai`
  - `openai_compatible`
- Added environment-driven compatible-provider support from:
  - `COMPAT_API_KEY`
  - `COMPAT_BASE_URL`
  - `COMPAT_MODEL_CANDIDATES`
- Added strict redaction for `COMPAT_API_KEY`-like secrets.
- Added provider-host sanitization so only a cleaned host is eligible for persistence.
- Added compatibility helpers for:
  - model-list discovery
  - capability probing
  - endpoint fallback ordering
  - explicit invalid-base-url detection

## Capability Probe Design

The compatible-provider runner now attempts the following ordered model list when model discovery succeeds:

1. `qwen3.7-max-2026-06-08`
2. `qwen3.7-max`
3. `deepseek-v4-pro`
4. `qwen3.7-plus`
5. `qwen3.6-flash`

For each existing model it probes, in order:

1. Responses API with strict JSON Schema
2. Chat Completions with `response_format=json_schema`
3. Chat Completions with JSON object
4. Plain Chat Completions with local strict JSON parsing

Local schema and semantic validation remain mandatory even when a provider supports structured outputs natively.

## Actual Third-Party Run Result

- Provider type: `openai_compatible`
- Execution date: `2026-07-14`
- SDK: `openai 2.45.0`
- Evidence directory:
  - `D:\home\fanys23\project_70\.local-evidence\openai-compatible-live-validation-20260714-034909`
- Summary file:
  - `D:\home\fanys23\project_70\.local-evidence\openai-compatible-live-validation-20260714-034909\openai-compatible-live-summary.json`

Observed blocker:

- The current PowerShell `COMPAT_BASE_URL` value is not a valid absolute `http(s)` URL.
- The runner stops before model-list discovery and before any live model request is sent.
- Therefore:
  - no model list was retrieved
  - no capability matrix was generated
  - no model was selected
  - no request id was produced
  - no token usage was produced
  - no raw live JSON response was produced
  - no schema validation ran on a live compatible-provider payload
  - no semantic validation ran on a live compatible-provider payload
  - no deterministic scenario projection was accepted
  - no simulator dry-run was accepted
  - no real Docker run was started for the compatible-provider live scenario

Current blocker classification:

- `invalid_base_url`
- message: `COMPAT_BASE_URL must be an absolute http(s) URL.`

This is an allowed real blocker under the bounded scope because the third-party base URL is not usable.

## Regression Status Around The Blocker

Lightweight regressions were rerun in WSL and passed:

- single-router dry-run
- two-router dry-run
- delay smoke real run
  - configured one-way delay: `30 ms`
  - measured average RTT: `70.414 ms`
  - throughput: `18.6 Mbps`
- packet-loss smoke real run
  - configured one-way loss: `3%`
  - measured packet loss: `12.0%`
  - throughput: `16.4 Mbps`
- invalid-scenario rejection evidence regenerated

Regression evidence:

- `D:\home\fanys23\project_70\.local-evidence\openai-live-regressions-20260714-114940`

## Security Notes

- No compatible-provider key value was printed in project artifacts.
- No key was written to `.env`, `runs`, `docs`, `metrics`, or Git.
- The runner now rejects malformed `COMPAT_BASE_URL` before any outbound live request.
- Evidence remains under `D:\home\fanys23\project_70\.local-evidence`.

## Official OpenAI Separation

- Official OpenAI API validation is tracked separately in `docs/progress/openai-live-validation-summary-2026-07-14.md`.
- Official OpenAI live status remains:
  - request reached OpenAI
  - HTTP `429`
  - `insufficient_quota`
  - incomplete for live generation and real Docker execution

## Next Safe Step

1. Correct `COMPAT_BASE_URL` so it is an absolute `http(s)` endpoint for the intended third-party OpenAI-compatible provider.
2. Rerun:

```powershell
Set-Location D:\home\fanys23\project_70
D:\home\fanys23\project_70\.venv-win311\Scripts\python.exe scripts\run_openai_live_validation.py --provider openai_compatible
```

3. After a valid base URL is present, the same runner will continue to:
  - model discovery
  - capability probing
  - live generation
  - local validation
  - dry-run
  - real WSL Docker execution
