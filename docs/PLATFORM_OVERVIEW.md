# AI Coder Platform

AI Coder is a local course-project platform that turns a software description and user-defined requirements into a runnable Python application and corresponding pytest tests. The selected task is a Board Game Turn Order Randomizer. The platform generates the application rather than serving a hand-written randomizer as its result.

## User workflow

1. Enter a description and edit the numbered requirements (`R1: ...`). Requirements remain user-controlled; automatic requirement drafting is not implemented.
2. Select **Generate application**. The platform plans interfaces, generates source and tests, and executes verification in Docker.
3. Inspect the run status, source, tests and execution evidence. Source and tests expand in place from a compact preview.
4. Review **MCP activity** and **Usage**, each with graphical and JSON views.
5. Download the run's ZIP. For a passed run, open the isolated preview and manually verify the application's behavior.

The interface uses a flexible input/result layout. Header placeholders reserve layout space without displaying metadata or exposing controls. Gradio's footer shortcuts are hidden.

## Architecture and roles

The Gradio UI calls a deterministic orchestrator. The orchestrator uses MCP clients to invoke three separate stdio MCP server processes. A shared server implementation exposes only the tools for its assigned role. Agent collaboration is mediated by the orchestrator through MCP tool results and typed artifacts; agents do not independently converse in an unbounded loop.

| Component | Responsibility | MCP tools |
|---|---|---|
| Planner | Convert the submitted requirements into public interfaces and acceptance criteria | `plan_requirements` |
| Developer | Generate application files and repair failures using execution feedback | `generate_application`, `repair_application` |
| Tester | Generate tests from requirements and agreed interfaces, plus requirement-to-test mappings | `generate_tests` |
| Orchestrator | Sequence work, preserve artifacts, enforce repair limits and test immutability | MCP client, not an LLM agent |
| Docker runner | Execute tests, check HTTP startup and manage previews | Deterministic infrastructure, not an agent |

Shared and role-specific `AGENT.md` instructions are loaded into Gemini system instructions. The configured default model is `gemini-3.5-flash-lite`; access depends on the user's Gemini project. The platform does not silently switch models.

## Bounded verification and recovery

Generated tests may be regenerated once for a syntax error **before first execution**. After execution starts, tests are locked. A failing application may receive at most two Developer repair rounds. Each revision is verified against the same tests.

- **PASSED:** collected tests and HTTP startup succeeded; manual UI acceptance is still separate.
- **FAILED:** application verification did not pass within the allowed workflow.
- **ERROR / NOT RUN:** inspect the retained detail to identify generation, infrastructure or execution prerequisites.

There is no additional Retry button or unlimited repair loop. **Generate application** already starts a new run from the current inputs, with fresh artifacts and additional usage. Re-running is not guaranteed to succeed. See [failure-handling decision](FAILURE_HANDLING_DECISION.md).

## Usage tracking

All Gemini requests use one adapter. The append-only ledger records an attempt before the request and saves returned `usage_metadata` before validating the generated response. Thus retries and malformed responses still count. Reports include API attempts, failed attempts, input/output/reasoning counts when supplied, provider totals and per-agent breakdowns.

Missing metadata is reported explicitly, not replaced by a measured zero. Missing reasoning detail does not imply that input, output or total usage was lost. Provider totals must not have reasoning added a second time. MCP tool calls and Docker executions are counted separately from model API attempts.

## Execution boundaries and artifacts

Tests run in Docker with networking disabled, a non-root user, read-only source/root filesystem and resource/time limits. Generated code receives no backend API key. The demo preview uses Docker bridge networking with a localhost-only published port; it can access the internet.

Each ignored `runs/<run_id>/` directory retains the request, specification, generated files, requirement mapping, trace, usage and execution reports. The shared ledger is `runs/usage.jsonl`. Do not delete it when reporting cumulative usage. Exported ZIPs exclude credentials.

The supported output stack is Python, Gradio and pytest with fixed dependencies. This is a local teaching/demo system, not a public multi-tenant execution service. Model-generated tests and mappings are evidence to inspect, not proof of complete correctness.

## Course rubric alignment

| Criterion | Platform support / demonstration responsibility |
|---|---|
| Multi-agent MCP demo (12 points) | Show real role-specific tools, client/server communication and coordinated generation/repair; explain the architecture. |
| In-class presentation (8 points) | Explain the chosen software, group-defined requirements, roles and MCP; prepare balanced delivery and timing. |
| Usage tracking (3 points) | Show API attempts, total tokens, missing metadata and agent-level breakdowns; explain the ledger. |
| UI (3 points) | Demonstrate editable inputs through generated executable source, tests, verification and preview. |
| Submission (1 point) | Submit the required repository ZIP and schedule the TA demo; these remain group actions. |

## Setup, evidence and attribution

Follow the [English run guide](RUN_GUIDE_EN.md) for installation, Docker setup and execution. The [development record](DEVELOPMENT.md) distinguishes historical live checks from offline tests and current limitations. A passed sample does not establish that every future generation will pass.

OpenHands was used as a conceptual reference, not copied implementation code. See [reference and attribution notes](OPENHANDS_REFERENCE.md). Dependencies retain their respective authorship and licenses.
