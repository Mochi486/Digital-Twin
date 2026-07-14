# OpenAI-Compatible Live Validation Summary

Date: 2026-07-14

## Scope

- Validate the bounded third-party `openai_compatible` provider path without relabeling it as `openai`.
- Use the fixed third-party model `qwen3.7-plus`.
- Use Chat Completions only, with ordered structured-output fallback.
- Complete live generation, local strict validation, dry-run, and real WSL Docker execution.

## Actual Third-Party Provider Used

- Provider type: `openai_compatible`
- Provider host saved in evidence: `ws-1s2sexxqtqluyr11.cn-beijing.maas.aliyuncs.com`
- Provider product: Alibaba Cloud Bailian OpenAI-compatible endpoint
- Base URL used for the live run:
  - `https://ws-1s2sexxqtqluyr11.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`
- Actual model: `qwen3.7-plus`
- Actual endpoint type: `chat.completions`
- Structured output mode selected: `response_format=json_schema`
- Native structured-output result: supported by the provider for this run
- Local schema validation: still applied after provider output
- Local semantic validation: still applied after provider output

## Capability Probe Result

This bounded run did not re-run model-list discovery because the fixed preflight result had already confirmed the target model:

- Preflight status: `PACKAGE_MODEL_PASS`
- Confirmed model: `qwen3.7-plus`

The live runner therefore probed only the required structured-output fallback order for the fixed model:

1. Chat Completions + `response_format=json_schema`
2. Chat Completions + `response_format=json_object`
3. Plain Chat Completions with local strict JSON parsing

The first mode succeeded, so no lower-priority mode was exercised.

Evidence:

- Summary JSON:
  - `D:\home\fanys23\project_70\.local-evidence\openai-compatible-live-validation-20260714-064525\openai-compatible-live-summary.json`
- Capability matrix:
  - `D:\home\fanys23\project_70\.local-evidence\openai-compatible-live-validation-20260714-064525\openai-compatible-capability-matrix.json`

## Live Model Generation Result

- Status: passed
- Request attempts used: `1`
- Request id: `chatcmpl-485e8a26-d032-9a72-b8e4-916ed3633461`
- Request latency: `85.478 s`
- Token usage:
  - prompt: `159`
  - completion: `2847`
  - total: `3006`
- Raw structured JSON saved: yes
- Raw response file:
  - `D:\home\fanys23\project_70\.local-evidence\openai-compatible-live-validation-20260714-064525\openai-compatible-attempt-01.json`

The model returned a valid six-node abstract routed topology:

- one client
- one server
- four routers
- six links
- two client-server paths
- `20 Mbps`
- `10 ms` one-way delay
- `0%` packet loss
- one TCP flow

## Validation and Deterministic Projection

All required local gates passed for the accepted live response:

- JSON parsing: passed
- JSON Schema validation: passed
- semantic validation: passed
- exactly 6 nodes: passed
- exactly 1 client: passed
- exactly 1 server: passed
- exactly 4 routers: passed
- connected topology: passed
- alternative-path validation: passed
- duplicate-link rejection: passed
- `20 Mbps` constraint: passed
- `10 ms` constraint: passed
- `0%` packet-loss constraint: passed
- forbidden-content rejection: passed
- deterministic subnet/IP allocation: passed
- deterministic static-route generation: passed
- route-conflict detection: passed
- simulator dry-run: passed

Normalization remained deterministic and was saved with before/after records in the attempt evidence.

## Real WSL Docker Execution

- Real Docker run status: passed
- Tracked run directory:
  - `D:\home\fanys23\project_70\runs\openai-compatible-live-validation-20260714-064525`
- Metrics file:
  - `D:\home\fanys23\project_70\runs\openai-compatible-live-validation-20260714-064525\metrics.json`
- Topology SVG:
  - `D:\home\fanys23\project_70\runs\openai-compatible-live-validation-20260714-064525\topology.svg`
- Host-routing preparation log:
  - `D:\home\fanys23\project_70\.local-evidence\openai-compatible-live-validation-20260714-064525\openai-compatible-prepare.log`
- Simulator log:
  - `D:\home\fanys23\project_70\.local-evidence\openai-compatible-live-validation-20260714-064525\openai-compatible-simulator.log`

Observed execution result:

- container count: `6`
- network count: `6`
- route verification: passed
- qdisc verification: passed
- alternative path count: `2`
- selected path:
  - `client-1 -> router-a -> router-b -> router-d -> server-1`
- hop count: `4`
- ping transmitted/received/loss:
  - `3 / 3 / 0%`
- ping RTT min/avg/max/mdev:
  - `61.127 / 82.194 / 122.359 / 28.411 ms`
- throughput:
  - `18.3 Mbps`
- configured bandwidth:
  - `20.0 Mbps`
- configured one-way delay:
  - `10.0 ms`
- configured packet loss:
  - `0.0%`
- stage timings:
  - setup total: `38.622 s`
  - ping stage: `2.182 s`
  - iperf stage: `7.401 s`
  - cleanup: `3.204 s`

Cleanup status:

- passed
- residual project containers: none
- residual project networks: none

## Regressions After Live Success

Regression evidence:

- `D:\home\fanys23\project_70\.local-evidence\openai-live-regressions-20260714-145315`

Results:

- unit tests: `43/43` passed
- single-router dry-run: passed
- two-router dry-run: passed
- one delay smoke real run: passed
  - configured one-way delay: `30 ms`
  - measured RTT average: `72.615 ms`
  - throughput: `18.6 Mbps`
- one packet-loss smoke real run: passed
  - configured one-way loss: `3%`
  - measured ping loss: `10.0%`
  - throughput: `13.8 Mbps`
- invalid AI scenario rejection: passed
- cleanup after regression: no residual project containers or networks

## Fixes Added During This Closure

- The generic topology live runner now reuses the first successful capability probe response instead of spending an extra live request.
- Host bridge routing preparation for WSL is now performed synchronously after Docker network creation and before traffic execution.
- The same WSL host-routing ordering fix was applied to the older single-router routed regression path.
- Combined qdisc application now preserves delay/loss and selected-path bandwidth shaping together on the same router egress interface.

## Security Notes

- No API key value was printed.
- No API key value was written to `.env`, docs, metrics, runs, evidence payloads, or Git.
- Only sanitized provider host, model, request id, usage, latency, and redacted non-sensitive payloads were persisted.
- Evidence paths were kept under:
  - `D:\home\fanys23\project_70\.local-evidence`

## Official OpenAI Separation

This file records only the third-party OpenAI-compatible provider path.

Official OpenAI API status remains separate and unchanged:

- request date: `2026-07-14`
- provider: `openai`
- result: HTTP `429`
- error code: `insufficient_quota`
- live official OpenAI generation, dry-run, and real Docker execution remain incomplete

See:

- `docs/progress/openai-live-validation-summary-2026-07-14.md`

## Outcome

Within the bounded non-DFN, non-RL scope, the third-party OpenAI-compatible live path is now complete:

- live generation: complete
- local strict validation: complete
- deterministic projection: complete
- dry-run: complete
- real WSL Docker execution: complete
- cleanup and lightweight regression closure: complete
