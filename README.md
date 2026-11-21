# AI Coder — Board Game Turn Order Randomizer

A small multi-agent system that accepts a software description and requirements, generates a Python/Gradio application and pytest tests through Gemini, executes them in Docker, and repairs application failures at most twice. The randomizer is the generation task, not a prewritten replacement for generated output.

## Setup

Requires Python 3.14+, Docker Desktop, and a Gemini API key with access to the configured model.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock.txt
cp .env.example .env
```

Edit `.env` locally. Set `GEMINI_API_KEY`; the requested model defaults to `gemini-3.5-flash-lite`. Do not commit the key. The application loads `.env` without overriding exported environment variables. Model availability and quota depend on your account; the application never switches models automatically.

```sh
docker build -t ai-coder-runner:1 runtime
python -m ai_coder.ui
```

Open the localhost address printed by Gradio. The runner image has the fixed Gradio/pytest dependencies; generated applications cannot install additional packages. The first image build needs network access, generated-code test execution does not.

## Workflow

1. Edit the description and numbered `R1: ...` requirements in the English UI.
2. Generate: Planner defines interfaces and acceptance criteria, Developer creates source, Tester creates tests independently from the implementation.
3. Invalid generated test syntax can be regenerated once before execution; tests are then locked. The runner executes pytest and checks that the generated application serves HTTP. Application failures can trigger two Developer repairs using unchanged tests.
4. Review the Overview tab for final test counts, startup verification, repair rounds and requirements needing manual review. Open the source, tests, requirement mappings, MCP calls and Gemini usage tabs for details. Download the ZIP for that run.
5. For a passed run, open the isolated preview and manually verify the UI. The preview link appears only after an HTTP readiness check (up to 30 seconds); startup failures include bounded container logs and trigger container cleanup. Stop the preview when finished.

`PASSED` means collected tests and the startup check passed, not that every requirement or UI interaction has been proven. Coverage mappings are model-authored and should be reviewed. `NOT RUN`, `FAILED` and `ERROR` are retained rather than converted to success. Starting a new generation clears the prior result and stops its preview.

## Architecture

A deterministic Gradio host coordinates three real STDIO MCP server processes. They share one server implementation but expose role-specific tools. Role instructions in `agents/COMMON.md` and `agents/<role>/AGENT.md` are loaded into Gemini system instructions. All model requests pass through one tracked adapter. No generated Python executes in the host process.

Application files: `app.py`, `logic.py`, `README.md`; test files: `tests/test_*.py`. The host supplies pinned `requirements.txt`. Generated artifacts and reports live under ignored `runs/<run_id>/`. `runs/usage.jsonl` is the persistent cumulative ledger; deleting it resets cumulative evidence. Unknown token counts are reported separately. MCP calls and test executions are not Gemini calls.

The Docker runner uses a non-root user, read-only source mount/root filesystem, no network, dropped capabilities, no backend credentials and bounded CPU/memory/time. Preview uses ordinary Docker bridge networking and a localhost-only port, as approved for the demo; it can access the internet. Test execution remains disconnected. It is intended for this local course demo, not a public multi-tenant code execution service.

## Development and verification

```sh
.venv/bin/python -m pytest tests -q
```

Offline workflow tests inject deterministic model/runner results; the MCP discovery test starts actual MCP processes. They do not establish that live Gemini generation or container execution succeeds. Latest offline validation: 37 system tests passed on November 20. In the historical live integration check, a generated application passed 11 tests after one Developer repair, with browser interactions inspected. Model outputs still require requirement review (that sample reset restores its initial example players). See the validation register in [DEVELOPMENT.md](docs/DEVELOPMENT.md) for the currently observed results.

- [Platform overview](docs/PLATFORM_OVERVIEW.md)
- [Failure-handling decision](docs/FAILURE_HANDLING_DECISION.md)
- [Run guide](docs/RUN_GUIDE_EN.md)
- [Living development record](docs/DEVELOPMENT.md)
- [High-level design](docs/FINAL_PROJECT_DESIGN.md)
- [Figma prototype and walkthrough](docs/FIGMA_PROTOTYPE_GUIDE.md)
- [OpenHands references and attribution](docs/OPENHANDS_REFERENCE.md)

OpenHands is conceptual reference only. No OpenHands implementation code has been copied. MCP, Google GenAI, Gradio and other dependencies remain their respective authors' work. The usage-ledger approach builds on the group's Assignment 2 work.
