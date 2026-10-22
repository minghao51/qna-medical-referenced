# Logfire dependency/API compatibility spike — 2026-10-16

**Status: spike complete; application tracing and package adoption are not approved by this report.** Logfire 5.2.0 APIs worked in an isolated, network-denied synthetic probe. The full-project resolver selected OpenTelemetry 1.45.1 and `protobuf` 6.33.6, a major `protobuf` change from the existing 4.25.9 lock. Stop before project dependency/lock adoption; that dependency set requires separate review/approval. No project package files or application code were changed.

## Scope and reproducibility

Work was confined to `/tmp/qna-resume-lKssxG9v/logfire-spike/` plus this report. Python 3.12.13 and uv 0.12.1 were already available. The project’s `pyproject.toml` and `uv.lock` were read/copied for scratch resolution only; their repository SHA-256 values remain `6080476f59308f9bd4c615788e6dc1f8efca4fd23d079561efbb35d9d455f1e8` and `10a308c18f3078abcade42024541464d3623d730af532b5f777f9298a0f7f8f5`, respectively.

The full-project scratch copy added only `logfire==5.2.0`, then resolved with all declared dependency groups, including `evaluation` (DeepEval/LangChain) and main dependencies including Chroma. `uv lock` resolved 312 packages; it did **not** install the project or its optional evaluation group. The separate runtime probe installed only its isolated 40-package closure, including `logfire[fastapi]==5.2.0` to exercise the documented FastAPI hook. Neither Pydantic AI, Pydantic Evals, DeepEval, nor Chroma was installed in that runtime environment. The Logfire `datasets` extra was not selected; it is the extra that declares Pydantic Evals.

**Package-registry/documentation access:** `uv lock`/`uv sync` used the public PyPI index (`https://pypi.org/simple`); public PyPI JSON metadata was fetched from `pypi.org`, and Logfire wheels from `files.pythonhosted.org`. Official docs were fetched from `pydantic.dev`. Legacy `logfire.pydantic.dev` documentation URLs returned HTTP 403; no credentials were supplied or used. No credential files or environment values were inspected or printed. No provider, hosted Logfire, app, or other runtime network call was made.

Reproduction artifacts:

- Full-project candidate copy and lock: `/tmp/qna-resume-lKssxG9v/logfire-spike/project/` (`uv.lock` SHA-256 `16764a6cad2039b17821e8a99f4905d3d2083f835d7d93e73f4ee3fc29e9d340`).
- Older-pin comparison copy: `/tmp/qna-resume-lKssxG9v/logfire-spike/compat-4.6/`.
- Runtime probe manifest and isolated environment: `/tmp/qna-resume-lKssxG9v/logfire-spike/probe/` (`probe/uv.lock` SHA-256 `efdf50e4c8427b37697c4054efe8fd49724dfd92b1994c3e332daa670a637b95`).
- Reproducible synthetic probe: `/tmp/qna-resume-lKssxG9v/logfire-spike/probe/probe.py` (SHA-256 `47cbb486da9265153203ba1baf7f226fb5b3559772be6a0174ade0e314eab5b8`); captured output is in `probe/probe-output.json` (SHA-256 `3f8eea13b755abb5f99d6a9a64592a83e32d9f0c71ff5bad08a8289a58b519b7`).

The probe process ran under `bwrap --unshare-net`, with a clean `env -i` environment and Python monkeypatches for socket connect and DNS calls installed before importing Logfire/OpenTelemetry. The sandbox had no network namespace; the probe recorded zero Python network/DNS attempts. Its command was:

```sh
bwrap --unshare-net --ro-bind / / --dev /dev --proc /proc \
  --bind /tmp/qna-resume-lKssxG9v/logfire-spike /tmp/qna-resume-lKssxG9v/logfire-spike \
  /usr/bin/env -i PATH=/usr/bin:/bin \
  HOME=/tmp/qna-resume-lKssxG9v/logfire-spike/probe/home \
  TMPDIR=/tmp/qna-resume-lKssxG9v/logfire-spike/probe/tmp \
  PYTHONDONTWRITEBYTECODE=1 \
  /tmp/qna-resume-lKssxG9v/logfire-spike/probe/.venv/bin/python \
  /tmp/qna-resume-lKssxG9v/logfire-spike/probe/probe.py
```

Probe manifest direct pins were Logfire 5.2.0 plus its FastAPI extra, FastAPI 0.129.0, Starlette 0.52.1, HTTPX 0.28.1, Pydantic 2.12.5/core 2.41.5, OTel API/SDK/OTLP HTTP exporter 1.45.1, semantic conventions 0.66b1, OTel instrumentation 0.66b1, protobuf 6.33.6, and typing-extensions 4.15.0. `uv sync --directory .../probe --no-install-project` installed these exact 40 packages (full lock is in scratch):

`annotated-doc==0.0.5`, `annotated-types==0.8.0`, `anyio==4.14.2`, `asgiref==3.12.1`, `certifi==2026.7.22`, `charset-normalizer==3.5.2`, `executing==2.3.0`, `fastapi==0.129.0`, `googleapis-common-protos==1.75.5`, `h11==0.16.0`, `httpcore==1.0.9`, `httpx==0.28.1`, `idna==3.20`, `logfire==5.2.0`, `markdown-it-py==4.2.0`, `mdurl==0.1.2`, `opentelemetry-api==1.45.1`, `opentelemetry-exporter-http-transport==0.66b1`, `opentelemetry-exporter-otlp-common==0.66b1`, `opentelemetry-exporter-otlp-proto-common==1.45.1`, `opentelemetry-exporter-otlp-proto-http==1.45.1`, `opentelemetry-instrumentation==0.66b1`, `opentelemetry-instrumentation-asgi==0.66b1`, `opentelemetry-instrumentation-fastapi==0.66b1`, `opentelemetry-proto==1.45.1`, `opentelemetry-sdk==1.45.1`, `opentelemetry-semantic-conventions==0.66b1`, `opentelemetry-util-http==0.66b1`, `packaging==26.3`, `protobuf==6.33.6`, `pydantic==2.12.5`, `pydantic-core==2.41.5`, `pygments==2.21.0`, `requests==2.34.2`, `rich==15.0.0`, `starlette==0.52.1`, `typing-extensions==4.15.0`, `typing-inspection==0.4.4`, `urllib3==2.8.0`, and `wrapt==2.5.1`.

The runtime probe used only synthetic markers. It did not certify application privacy, all exporters, or hosted behavior. No application/backend pytest was run. The parent-reported 819 passed / 6 skipped gate is inherited evidence only, not a test result from this spike.

## Existing repository boundaries inspected

- `pyproject.toml` has no direct Logfire or application OTel dependency. `uv.lock` currently resolves transitive `opentelemetry-api`, SDK, OTLP gRPC/common, and proto at **1.27.0**, semantic conventions at **0.48b0**, and protobuf at **4.25.9**. Chroma 1.5.5 and the optional evaluation group’s DeepEval 3.9.7 are already in the lock.
- `src/app/logging.py` configures root stream logging and JSON `log_event` fields. `RequestIDMiddleware` generates an ID and logs method/path/status/latency plus `auth_key_id`; `src/app/routes/chat.py` includes the request ID in terminal SSE/error events. These are not currently forwarded to Logfire.
- `src/app/factory.py` configures logging at import and owns app construction/cleanup in lifespan. It closes the app-created LLM client and resets logical state; there is no Logfire lifecycle hook or flush/shutdown today.
- `src/rag/trace_models.py` shows `PipelineTrace` can hold the raw query, retrieved `RetrievedDocument.content`, and `ContextStage.preview`. Do not export these objects wholesale.
- Current W&B tracking selects structural fields/metrics through allowlists. Raw run-directory artifact upload is only enabled when `tracking.wandb.log_artifacts is True`, and logs a warning that this is not content-policy approval. No Logfire exporter exists.

## Candidate resolution and transitive effects

PyPI reported **Logfire 5.2.0** as current `logfire` release during the spike. Wheel: `logfire-5.2.0-py3-none-any.whl`, SHA-256 `c73dd02cfe048f2254e803962aa992d7f53217d121f3488e797926c30442342c`. Its base metadata requires Python >=3.10; OTel API, SDK, and OTLP HTTP exporter `>=1.39,<1.46`; OTel instrumentation `>=0.41b0,<0.67b0`; semantic conventions `>=0.60b0,<0.67b0`; plus protobuf >=4.23.4, requests, rich, executing, and typing-extensions. The optional `fastapi` extra adds FastAPI instrumentation; the optional `datasets` extra adds Pydantic Evals and was not selected.

Scratch command (full project, copied lock/pyproject; the dependency group constraints were included):

```sh
UV_DEFAULT_INDEX=https://pypi.org/simple \
  uv lock --directory /tmp/qna-resume-lKssxG9v/logfire-spike/project

UV_DEFAULT_INDEX=https://pypi.org/simple \
UV_CACHE_DIR=/tmp/qna-resume-lKssxG9v/logfire-spike/uv-cache \
  uv lock --directory /tmp/qna-resume-lKssxG9v/logfire-spike/probe
UV_DEFAULT_INDEX=https://pypi.org/simple \
UV_CACHE_DIR=/tmp/qna-resume-lKssxG9v/logfire-spike/uv-cache \
  uv sync --directory /tmp/qna-resume-lKssxG9v/logfire-spike/probe --no-install-project
```

The Logfire 4.6.0 and 5.2.0 wheel files were downloaded directly from the `files.pythonhosted.org` URLs returned by their public PyPI JSON metadata; only 5.2.0 was installed (in the isolated probe venv).

Resolver delta against the repository lock (308 → 312 packages):

- Added: `logfire==5.2.0`, `opentelemetry-exporter-http-transport==0.66b1`, `opentelemetry-exporter-otlp-common==0.66b1`, `opentelemetry-exporter-otlp-proto-http==1.45.1`, `opentelemetry-instrumentation==0.66b1`.
- Removed: `deprecated==1.3.1`.
- Updated: OTel API 1.27.0 → 1.45.1; OTLP proto common and gRPC exporter 1.27.0 → 1.45.1; OTel proto 1.27.0 → 1.45.1; OTel SDK 1.27.0 → 1.45.1; semantic conventions 0.48b0 → 0.66b1; protobuf 4.25.9 → 6.33.6.
- Chroma and DeepEval remained at 1.5.5 and 3.9.7 in this candidate resolution; no evaluation dependencies were installed. No other package version changes appeared in the full candidate lock diff.

The protobuf major change is confirmed by the resolved `opentelemetry-proto==1.45.1` metadata (`protobuf>=5.0,<8.0`), versus OTel proto 1.27.0 (`protobuf>=3.19,<5.0`). This crosses the explicit stop condition: **do not adopt/update the project lock in this spike.** OTel’s 1.x version change is not itself a major, but it also requires reviewing the whole transitive SDK set.

A metadata/lock-only fallback check used **Logfire 4.6.0** (wheel downloaded for source inspection, SHA-256 `d322844db7a2f1935976f2852a07e3753489ecc4e83fa288173b05a453bb1cbf`; not installed). Its metadata allows OTel SDK/OTLP HTTP exporter `>=1.21,<1.37`, but the unpinned full-project resolver still chose OTel 1.36.0, semantic conventions 0.57b0, protobuf 6.33.6, and downgraded wrapt 2.1.2 → 1.17.3. It is not a clean fallback without further explicit transitive constraints; those constraints and runtime APIs were not tested. No exact candidate is cleared for project adoption under the current lock policy.

## Exact-version API/source and runtime findings

The 5.2.0 wheel source and current official docs confirm:

- `logfire.configure(local=True, send_to_logfire=False, console=False, additional_span_processors=[...])` is supported. `local=True` means a separate `Logfire` configuration object; it **does not** mean local-only/no-send. The API defaults `send_to_logfire` to true when unset and can load `LOGFIRE_TOKEN`/`LOGFIRE_API_KEY`; future local/disabled mode must set no-send explicitly and avoid inheriting credentials.
- `console=False` disables the Logfire console exporter. The probe inspected the resolved config (`send_to_logfire is False`, `console is False`), captured zero stdout/stderr bytes, and emitted spans into the OTel `InMemorySpanExporter` through `SimpleSpanProcessor`. `force_flush(1000)` and `shutdown(1000)` returned true in the normal synthetic case. The probe ran in a network namespace with no egress and no token; it observed no socket/DNS attempts.
- The source separately honors standard `OTEL_EXPORTER_OTLP_*`/`OTEL_*_EXPORTER` environment configuration. Therefore `send_to_logfire=False` alone is not a sufficient policy against every possible external OTel exporter; the probe used a clean environment, and a future app slice must explicitly control this separate exporter path.
- Parent/child manual spans shared a trace ID and the child’s parent span ID matched the request span. The request ID was attached as an explicit safe synthetic attribute; propagation from `request.state.request_id` is not automatic and remains application work.
- A span context manager recorded a raised synthetic exception. The in-memory span contained its synthetic exception message and scratch traceback path. The exact 5.2.0 `scrubbing.py` source treats `exception.message` and `exception.stacktrace` as safe keys (and notes old exception-message scrubbing was removed); path/URL attributes are also among safe keys. Do not rely on default scrubbing to remove exception text, stack paths, request arguments, or application content.
- `logfire[fastapi]` is required for the FastAPI API. With `capture_headers=False` and default `record_send_receive=False`, default FastAPI instrumentation still captured a synthetic request-body value through validated endpoint arguments. A `request_attributes_mapper` returning `{}` removed that value in the in-memory trace. A future mapper must use a reviewed allowlist; disabling header/body capture alone is not enough.
- `inspect_arguments=False` is supported, but does not suppress FastAPI endpoint argument capture. `ScrubbingOptions(extra_patterns=...)` replaced the matched synthetic substring in the attribute, but the serialized `logfire.scrubbed` note still contained the matched substring. A callback returning a fixed `[REDACTED]` value removed the synthetic marker from that probe trace. This is one synthetic test, not a certification; custom scrubbing is not a substitute for per-boundary field allowlists.
- `force_flush(timeout_millis=...)` and `shutdown(timeout_millis=..., flush=...)` are supported and return boolean status. A deliberately slow synthetic `SpanProcessor` received a ~3 ms flush budget for a 5 ms call, returned false, and took ~60 ms. A 5 ms shutdown with `flush=False` also returned false after ~60 ms because synchronous processor shutdown can overrun the requested timeout. The SDK exposes/cooperatively passes timeout budgets but cannot forcibly interrupt an unresponsive synchronous exporter/processor; do not claim a strict wall-clock deadline without a separately tested wrapper/process boundary.

Runtime output summary: no network/DNS attempts; console output 0 bytes; 3 in-memory manual spans; correlation passed; exception message/path present; FastAPI default body canary present and mapper-controlled canary absent; custom-pattern note retained a canary; callback replacement removed it; normal flush/shutdown true; slow flush/shutdown false and overran the requested timeout. Exact JSON evidence is `probe/probe-output.json`.

## Official links

- [Logfire PyPI release/metadata](https://pypi.org/project/logfire/5.2.0/) and [JSON metadata](https://pypi.org/pypi/logfire/5.2.0/json)
- [Logfire API reference: configure, force_flush, shutdown, FastAPI instrumentation](https://pydantic.dev/docs/logfire/api/logfire/)
- [FastAPI integration and captured fields](https://pydantic.dev/docs/logfire/integrations/web-frameworks/fastapi/)
- [Manual spans and exception recording](https://pydantic.dev/docs/logfire/instrument/python/add-manual-tracing/)
- [Sensitive-data scrubbing](https://pydantic.dev/docs/logfire/instrument/python/scrubbing/)
- [Testing/local in-memory exporter guidance](https://pydantic.dev/docs/logfire/reference/testing/)
- [OTel proto 1.45.1 package metadata](https://pypi.org/project/opentelemetry-proto/1.45.1/)

## Decision and remaining blockers

1. **Do not change `pyproject.toml`, `uv.lock`, the application, or tests based on this spike.** The separate project-lock adoption review must explicitly approve Logfire 5.2.0 and the resulting OpenTelemetry/protobuf set, or authorize a focused compatible-version/constraint investigation. The 4.6.0 metadata result is not runtime approval.
2. Before an application tracing slice, approve exact capture allowlists for request IDs, FastAPI values, RAG traces, evaluation cases, and exception/error paths; separately constrain `OTEL_EXPORTER_OTLP_*` environment behavior. Do not instrument/export the current request log or `PipelineTrace` wholesale.
3. Future lifecycle integration must be separately designed/tested against the app lifespan and exporter failure behavior. These SDK timeout parameters are not a hard bound for synchronous uncooperative exporters.
4. No hosted Logfire token/project/region/access/retention was configured or tested. No hosted export, privacy certification, real data, application tracing, SDK upgrade, or application/backend pytest is claimed.

## Durable standalone reproduction

Parent independently reran the network-isolated probe and asserted the correlation, no-send/console-off, canary capture/control and timeout-overrun findings. This appendix preserves the actual probe and installed package pins so the original scratch directory is not required. Exact elapsed milliseconds and trace IDs vary; the observed content/control outcomes are the evidence, not a hard deadline guarantee.

Create a **new scratch directory**, copy the following manifest to `pyproject.toml`, the package pins to `requirements.txt`, and the script to `probe.py`. Package installation is the approved registry-access step; it is not a runtime probe and must remain outside the project environment. Do not install these pins into the application or change its lock.

```toml
[project]
name = "logfire-compatibility-probe"
version = "0.0.0"
requires-python = ">=3.12,<3.13"
dependencies = [
    "logfire[fastapi]==5.2.0",
    "fastapi==0.129.0",
    "pydantic==2.12.5",
    "pydantic-core==2.41.5",
    "typing-extensions==4.15.0",
    "starlette==0.52.1",
    "httpx==0.28.1",
    "opentelemetry-api==1.45.1",
    "opentelemetry-sdk==1.45.1",
    "opentelemetry-exporter-otlp-proto-http==1.45.1",
    "opentelemetry-semantic-conventions==0.66b1",
    "opentelemetry-instrumentation==0.66b1",
    "protobuf==6.33.6",
]
```

Installed closure (40 packages):

```text
Pygments==2.21.0
annotated-doc==0.0.5
annotated-types==0.8.0
anyio==4.14.2
asgiref==3.12.1
certifi==2026.7.22
charset-normalizer==3.5.2
executing==2.3.0
fastapi==0.129.0
googleapis-common-protos==1.75.5
h11==0.16.0
httpcore==1.0.9
httpx==0.28.1
idna==3.20
logfire==5.2.0
markdown-it-py==4.2.0
mdurl==0.1.2
opentelemetry-api==1.45.1
opentelemetry-exporter-http-transport==0.66b1
opentelemetry-exporter-otlp-common==0.66b1
opentelemetry-exporter-otlp-proto-common==1.45.1
opentelemetry-exporter-otlp-proto-http==1.45.1
opentelemetry-instrumentation-asgi==0.66b1
opentelemetry-instrumentation-fastapi==0.66b1
opentelemetry-instrumentation==0.66b1
opentelemetry-proto==1.45.1
opentelemetry-sdk==1.45.1
opentelemetry-semantic-conventions==0.66b1
opentelemetry-util-http==0.66b1
packaging==26.3
protobuf==6.33.6
pydantic==2.12.5
pydantic_core==2.41.5
requests==2.34.2
rich==15.0.0
starlette==0.52.1
typing-inspection==0.4.4
typing_extensions==4.15.0
urllib3==2.8.0
wrapt==2.5.1
```

After copying those three blocks into a fresh scratch directory, provision and execute there (substitute its absolute path for `ROOT`):

```bash
ROOT=/absolute/path/to/new/logfire-spike
uv venv --python 3.12 "$ROOT/.venv"
uv pip install --python "$ROOT/.venv/bin/python" -r "$ROOT/requirements.txt"
mkdir -p "$ROOT/config" "$ROOT/data" "$ROOT/home" "$ROOT/tmp"
bwrap --unshare-net --ro-bind / / --dev /dev --proc /proc \\
  --bind "$ROOT" "$ROOT" \\
  /usr/bin/env -i PATH=/usr/bin:/bin HOME="$ROOT/home" TMPDIR="$ROOT/tmp" \\
  PYTHONDONTWRITEBYTECODE=1 "$ROOT/.venv/bin/python" "$ROOT/probe.py"
```

The network namespace and clean environment are part of the probe contract; do not silently drop them. No application imports, real token or hosted endpoint is needed. The script uses only synthetic in-process FastAPI requests and in-memory exporters. It deliberately demonstrates unsafe defaults; it is **not** an application tracing integration.

```python
"""Synthetic Logfire 5.2.0 compatibility probe; run under bwrap --unshare-net."""

# This guard executes before importing Logfire or any OpenTelemetry SDK module.
import socket

blocked_network_calls: list[str] = []


def _deny_network(name: str):
    def denied(*args, **kwargs):
        blocked_network_calls.append(name)
        raise RuntimeError(f"network disabled by synthetic probe: {name}")

    return denied


socket.socket.connect = _deny_network("socket.connect")
socket.socket.connect_ex = _deny_network("socket.connect_ex")
socket.create_connection = _deny_network("socket.create_connection")
socket.getaddrinfo = _deny_network("socket.getaddrinfo")
socket.gethostbyname = _deny_network("socket.gethostbyname")
socket.gethostbyaddr = _deny_network("socket.gethostbyaddr")

import io
import json
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import SpanProcessor
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import logfire

BASE = Path(__file__).resolve().parent
CONFIG = BASE / "config"
DATA = BASE / "data"


def _span_data(exporter):
    spans = exporter.get_finished_spans()
    records = []
    for span in spans:
        events = [
            {"name": event.name, "attributes": dict(event.attributes or {})}
            for event in span.events
        ]
        records.append(
            {
                "name": span.name,
                "trace_id": span.context.trace_id,
                "span_id": span.context.span_id,
                "parent_span_id": span.parent.span_id if span.parent else None,
                "attributes": dict(span.attributes or {}),
                "events": events,
            }
        )
    return records


def _configure(exporter, *, scrubbing=None):
    return logfire.configure(
        local=True,
        send_to_logfire=False,
        console=False,
        token=None,
        api_key=None,
        config_dir=CONFIG,
        data_dir=DATA,
        inspect_arguments=False,
        scrubbing=scrubbing,
        additional_span_processors=[SimpleSpanProcessor(exporter)],
    )


def _build_app():
    app = FastAPI()

    @app.post("/synthetic")
    async def endpoint(payload: dict):
        return {"ok": True}

    return app


def main():
    emitted = io.StringIO()
    core_exporter = InMemorySpanExporter()
    with redirect_stdout(emitted), redirect_stderr(emitted):
        core = _configure(core_exporter)
        try:
            with core.span("synthetic request", request_id="synthetic-request-id"):
                with core.span("synthetic retrieval", stage="retrieval"):
                    core.info("synthetic event", result_count=1)
                raise RuntimeError("SYNTHETIC_EXCEPTION_CANARY")
        except RuntimeError:
            # The span context manager automatically records this exception.
            pass
        core_flush_ok = core.force_flush(timeout_millis=1000)
        core_shutdown_ok = core.shutdown(timeout_millis=1000)

        default_exporter = InMemorySpanExporter()
        default = _configure(default_exporter)
        default_app = _build_app()
        with default.instrument_fastapi(default_app, capture_headers=False):
            with TestClient(default_app) as client:
                response = client.post(
                    "/synthetic",
                    json={"body_text": "SYNTHETIC_BODY_CANARY"},
                )
                assert response.status_code == 200
        default.force_flush(timeout_millis=1000)
        default_shutdown_ok = default.shutdown(timeout_millis=1000)

        controlled_exporter = InMemorySpanExporter()
        controlled = _configure(controlled_exporter)
        controlled_app = _build_app()
        with controlled.instrument_fastapi(
            controlled_app,
            capture_headers=False,
            request_attributes_mapper=lambda request, attributes: {},
        ):
            with TestClient(controlled_app) as client:
                response = client.post(
                    "/synthetic",
                    json={"body_text": "SYNTHETIC_BODY_CANARY"},
                )
                assert response.status_code == 200
        controlled.force_flush(timeout_millis=1000)
        controlled_shutdown_ok = controlled.shutdown(timeout_millis=1000)

        scrub_exporter = InMemorySpanExporter()
        scrubbed = _configure(
            scrub_exporter,
            scrubbing=logfire.ScrubbingOptions(
                extra_patterns=["SYNTHETIC_CUSTOM_VALUE_CANARY"]
            ),
        )
        with scrubbed.span(
            "scrub probe", payload="prefix:SYNTHETIC_CUSTOM_VALUE_CANARY:suffix"
        ):
            pass
        scrubbed.force_flush(timeout_millis=1000)
        scrubbed_shutdown_ok = scrubbed.shutdown(timeout_millis=1000)

        callback_exporter = InMemorySpanExporter()
        callback_scrubbed = _configure(
            callback_exporter,
            scrubbing=logfire.ScrubbingOptions(
                extra_patterns=["SYNTHETIC_CALLBACK_VALUE_CANARY"],
                callback=lambda match: "[REDACTED]",
            ),
        )
        with callback_scrubbed.span(
            "callback scrub probe", payload="prefix:SYNTHETIC_CALLBACK_VALUE_CANARY:suffix"
        ):
            pass
        callback_scrubbed.force_flush(timeout_millis=1000)
        callback_shutdown_ok = callback_scrubbed.shutdown(timeout_millis=1000)

    core_spans = _span_data(core_exporter)
    default_capture = json.dumps(_span_data(default_exporter), default=str)
    controlled_capture = json.dumps(_span_data(controlled_exporter), default=str)
    scrub_spans = _span_data(scrub_exporter)
    scrub_capture = json.dumps(scrub_spans, default=str)
    callback_capture = json.dumps(_span_data(callback_exporter), default=str)
    scrub_marker_paths = []

    def find_marker_paths(value, path="$"):
        if isinstance(value, dict):
            for key, item in value.items():
                find_marker_paths(item, f"{path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                find_marker_paths(item, f"{path}[{index}]")
        elif isinstance(value, str) and "SYNTHETIC_CUSTOM_VALUE_CANARY" in value:
            scrub_marker_paths.append(path)

    find_marker_paths(scrub_spans)
    root = next(item for item in core_spans if item["name"] == "synthetic request")
    child = next(item for item in core_spans if item["name"] == "synthetic retrieval")
    core_capture = json.dumps(core_spans, default=str)

    class SlowProcessor(SpanProcessor):
        def __init__(self):
            self.flush_timeout = None
            self.shutdown_called = False

        def on_start(self, span, parent_context=None):
            pass

        def on_end(self, span):
            pass

        def force_flush(self, timeout_millis=30000):
            self.flush_timeout = timeout_millis
            time.sleep(0.06)
            return False

        def shutdown(self):
            self.shutdown_called = True
            time.sleep(0.06)

    slow_processor = SlowProcessor()
    slow_local = logfire.configure(
        local=True,
        send_to_logfire=False,
        console=False,
        token=None,
        api_key=None,
        config_dir=CONFIG,
        data_dir=DATA,
        additional_span_processors=[slow_processor],
    )
    start = time.monotonic()
    slow_flush_ok = slow_local.force_flush(timeout_millis=5)
    slow_flush_elapsed_ms = (time.monotonic() - start) * 1000
    start = time.monotonic()
    slow_shutdown_ok = slow_local.shutdown(timeout_millis=5, flush=False)
    slow_shutdown_elapsed_ms = (time.monotonic() - start) * 1000

    result = {
        "logfire_version": __import__("importlib.metadata").metadata.version("logfire"),
        "fastapi_extra_installed": True,
        "resolved_send_to_logfire_false": core.config.send_to_logfire is False,
        "resolved_console_false": core.config.console is False,
        "network_attempts_blocked": blocked_network_calls,
        "captured_console_output_bytes": len(emitted.getvalue().encode()),
        "in_memory_local_export_span_count": len(core_spans),
        "correlation_same_trace": root["trace_id"] == child["trace_id"],
        "correlation_child_parent_matches": child["parent_span_id"] == root["span_id"],
        "exception_message_in_local_spans": "SYNTHETIC_EXCEPTION_CANARY" in core_capture,
        "exception_stack_path_present": str(BASE) in core_capture,
        "fastapi_default_body_canary_captured": "SYNTHETIC_BODY_CANARY" in default_capture,
        "fastapi_mapper_body_canary_captured": "SYNTHETIC_BODY_CANARY" in controlled_capture,
        "custom_scrub_canary_remains": "SYNTHETIC_CUSTOM_VALUE_CANARY" in scrub_capture,
        "custom_scrub_canary_paths": scrub_marker_paths,
        "custom_scrub_payload_value": scrub_spans[0]["attributes"].get("payload"),
        "custom_scrub_notes": scrub_spans[0]["attributes"].get("logfire.scrubbed"),
        "callback_scrub_canary_remains": "SYNTHETIC_CALLBACK_VALUE_CANARY" in callback_capture,
        "callback_scrub_shutdown_return": callback_shutdown_ok,
        "normal_force_flush_return": core_flush_ok,
        "normal_shutdown_return": core_shutdown_ok,
        "default_fastapi_shutdown_return": default_shutdown_ok,
        "controlled_fastapi_shutdown_return": controlled_shutdown_ok,
        "scrubbed_shutdown_return": scrubbed_shutdown_ok,
        "slow_force_flush_return": slow_flush_ok,
        "slow_force_flush_timeout_argument_ms": slow_processor.flush_timeout,
        "slow_force_flush_elapsed_ms": round(slow_flush_elapsed_ms, 1),
        "slow_shutdown_return": slow_shutdown_ok,
        "slow_shutdown_called": slow_processor.shutdown_called,
        "slow_shutdown_elapsed_ms": round(slow_shutdown_elapsed_ms, 1),
    }
    print(json.dumps(result, sort_keys=True, indent=2))
    assert not blocked_network_calls, f"unexpected attempted network/DNS: {blocked_network_calls}"
    assert core.config.send_to_logfire is False and core.config.console is False
    assert core_flush_ok is True and core_shutdown_ok is True and default_shutdown_ok is True
    assert controlled_shutdown_ok is True and scrubbed_shutdown_ok is True
    assert root["trace_id"] == child["trace_id"]
    assert child["parent_span_id"] == root["span_id"]


if __name__ == "__main__":
    main()
```
