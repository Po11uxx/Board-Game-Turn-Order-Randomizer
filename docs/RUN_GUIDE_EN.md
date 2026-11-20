# AI Coder Run Guide

Updated: November 19, 2026. This guide covers the Python, Gradio, Gemini, MCP and Docker implementation. Commands use macOS zsh/bash syntax.

> At the time of writing, the implementation is on the local `feature/ai-coder` branch and has not been committed or pushed. Team members need the complete implementation, including `ai_coder/`; cloning the earlier design-only GitHub revision is not sufficient.

## 1. Daily startup

If setup is already complete, start Docker Desktop and wait until its engine is running. In a terminal, change to your project directory and run:

```sh
# Replace this example path with your local checkout.
cd "/path/to/Board-Game-Turn-Order-Randomizer"
source .venv/bin/activate
docker info --format '{{.ServerVersion}}'
python -m ai_coder.ui
```

Open the address printed by Gradio, normally `http://127.0.0.1:7860`. Use the address from the current launch. The generated application's preview uses a separate, dynamically assigned port.

Keep the terminal running. Avoid launching multiple AI Coder instances. After editing `.env` or Python code, stop the process with `Ctrl+C` and restart it.

You do not need to reinstall dependencies or rebuild the image on every launch. Rebuild when `runtime/` changes or the image is missing; reinstall when project dependencies change.

## 2. First-time setup

### Prerequisites

- Python 3.14 or later. The recorded local validation used Python 3.14.2.
- Docker Desktop installed and running.
- Network access to Gemini. Dependency installation and the initial image build also require network access.
- A Gemini API key with access to the selected model. The configured model is `gemini-3.5-flash-lite`; availability depends on the account.

Check your environment:

```sh
python3 --version
docker --version
docker info --format '{{.ServerVersion}}'
```

`docker --version` only checks that the CLI exists. A successful `docker info` confirms that the engine is reachable.

### Install Python dependencies

From the project root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock.txt
```

If a working `.venv` already exists, activate it rather than recreating it. Do not copy another computer's virtual environment.

### Configure Gemini

Create `.env` only if it does not already exist, so an existing key is not overwritten:

```sh
if [ ! -f .env ]; then
  cp .env.example .env
fi
```

Edit the project-root `.env` locally:

```dotenv
GEMINI_API_KEY=replace_with_your_real_key
GEMINI_MODEL=gemini-3.5-flash-lite
```

Replace the placeholder with your key. Do not include real keys in source code, screenshots, chat messages or commits. `.env` is excluded by `.gitignore`.

The application loads `.env` at startup without overriding variables already exported in the terminal. To explicitly use the file's values:

```sh
unset GEMINI_API_KEY GEMINI_MODEL
python -m ai_coder.ui
```

The UI label **Configured (connection not verified)** means a key is configured; it does not prove that account access or connectivity works. A real generation makes actual API requests. The application never automatically switches to another model.

### Build the execution image

From the project root:

```sh
docker build -t ai-coder-runner:1 runtime
docker image inspect ai-coder-runner:1 --format '{{.Id}}'
```

Keep the image name `ai-coder-runner:1`, which the runner expects. The first build downloads dependencies; subsequent builds can reuse cached layers. Rebuild after changing `runtime/Dockerfile` or `runtime/entry.py`.

## 3. Generate an application

1. Check the model name and backend key status in the UI.
2. Enter the application description in **Software description**. The default is Board Game Turn Order Randomizer.
3. Enter one numbered requirement per line in **Requirements**, using unique IDs:

   ```text
   R1: Accept between 2 and 20 players.
   R2: Reject blank or duplicate player names.
   R3: Display a random permutation containing every player once.
   ```

   These three lines illustrate the format. Keep the complete default R1–R8 for the full Randomizer demo. If Reset must empty the fields, explicitly require it to “clear all names rather than restore example players.”

4. Click **Generate application** and watch the stages:

   ```text
   Planning → Developing → Generating tests → Executing
                                                ↓ on application failure
                                           Repairing → Executing
   ```

5. Before the first execution, invalid Python test syntax may be sent back to Tester for one regeneration. Once execution begins, tests are locked. Developer can repair application code at most twice.
6. Inspect the final status and result tabs.

| Tab or control | Contents |
|---|---|
| Application | Generated Python application source |
| Tests | pytest source, execution results, specification and requirement mapping |
| MCP activity | Actual tool calls, roles, statuses and durations |
| Usage | Per-run, cumulative and per-agent API/token accounting |
| Download this run | ZIP of available artifacts, including failed or incomplete runs |

Each instance processes one generation at a time. Starting another generation clears the previous UI result and stops the preview managed by that instance. Previous run directories remain on disk.

## 4. Interpret final statuses

| Status | Meaning and next step |
|---|---|
| PASSED | Collected tests and the application startup check passed. Continue manual requirement and UI review. |
| FAILED | Application verification still failed after the repair limit. Inspect the report rather than presenting it as a successful run. |
| NOT RUN | Docker/the image is unavailable, or execution cannot run. Read the reported reason. |
| ERROR | A model request, output validation, test generation/collection or execution infrastructure failed. Inspect the details. |

`PASSED` does not prove that every requirement is satisfied. Review input validation, button behavior and the model-generated coverage mapping. The reviewed example restores its initial example players on Reset and clears the result; it does not clear all names.

If Docker or the image is unavailable during preflight, generation stops before spending model requests. Do not bypass this check by running unreviewed generated code on the host.

## 5. Open and stop the generated application

For a passed run, click **Open isolated preview**. Open the displayed link, such as `http://127.0.0.1:53859`. The port may change each time. If the application is still starting, refresh after it has had time to initialize.

Verify that:

- Valid inputs produce a numbered order containing every player exactly once.
- Duplicate or blank names, fractional/out-of-range counts and count mismatches produce errors.
- Reshuffle retains the same players. Repeated random orders are valid.
- Edit and Reset behave as specified in the input requirements.

Click **Stop preview** when finished. Normal AI Coder shutdown also attempts to stop its managed preview.

Test containers have no network access. Under the approved demo configuration, preview containers use ordinary Docker bridge networking and can access the internet, but publish only a localhost port. Neither receives the Gemini key; both use a non-root user, read-only mounts and resource limits. The runtime disables Gradio browser run history.

## 6. Artifacts and cumulative usage

Artifacts are stored beneath the project root:

```text
runs/
  usage.jsonl                    Persistent ledger of actual API attempts
  <run_id>/
    request.json                 Original description and requirements
    spec.json                    Planner specification, when produced
    generated/                   Source, README, dependencies and tests
    coverage.json                Requirement-to-test mapping
    reports.json                 Execution and repair history, when available
    trace.json                   MCP tool-call trace
    usage.json                   Usage snapshot at run completion
    result.json                  Final status and failure reason
    manifest.json                Artifact hashes and verification status
    rejected_tests.json          Rejected tests if regeneration was triggered
    project.zip                  Downloadable bundle
```

Files for later stages may be absent when a run fails early.

- Every actual API attempt counts, including retries, repairs and recorded connection diagnostics.
- `unknown_usage_calls` counts requests without provider total-token metadata. The known token sum is not a complete total including those requests.
- Zero reasoning tokens accompanied by a nonzero unknown count does not establish zero reasoning consumption.
- MCP calls and runner invocations are separate from Gemini API calls.
- `usage.json` is a snapshot. To inspect the latest cumulative ledger without calling Gemini:

```sh
python -c 'from pathlib import Path; from ai_coder.usage import Ledger; print(Ledger(Path("runs/usage.jsonl")).summary())'
```

Do not delete the ledger to reset demo statistics. Failed requests are part of the usage evidence.

## 7. Run a downloaded application separately

Read the ZIP's `README.md` first. Its **Runtime setup (provided by AI Coder)** section documents dependencies, privacy settings and startup commands.

For source you have reviewed and chosen to execute on your computer, create a separate virtual environment in the extracted application directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export GRADIO_RUN_HISTORY=False
export GRADIO_ANALYTICS_ENABLED=False
python -m pytest tests
python app.py
```

These commands execute code on the host. Continue using AI Coder's Docker runner/preview for unreviewed output. The generated Randomizer does not need a Gemini key.

If AI Coder already occupies port 7860, start the generated application on another port:

```sh
GRADIO_SERVER_PORT=7861 python app.py
```

## 8. Test AI Coder itself

Run this from the AI Coder project root, not the generated application's directory:

```sh
.venv/bin/python -m pytest tests -q
```

The current recorded result is 32 passing tests. The suite includes real stdio MCP process discovery, but some workflow tests use model/runner substitutes. It does not replace a live Gemini + Docker generation and does not spend Gemini API calls.

The repository's `tests/` tests AI Coder. The ZIP's `tests/` tests the generated application.

## 9. Shutdown and cleanup

1. Click **Stop preview**.
2. Press `Ctrl+C` in the terminal running AI Coder.
3. Optionally run `deactivate` to leave the virtual environment.

After an abrupt shutdown, inspect project containers:

```sh
docker ps -a --filter 'name=ai-coder-' --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

After confirming a specific container belongs to a finished demo, replace the example suffix below with its exact name:

```sh
docker rm -f ai-coder-preview-REPLACE_WITH_ACTUAL_SUFFIX
```

Do not remove unrelated Docker containers. Separately launched inspection previews may not be managed by the UI's Stop preview control; their cleanup details are recorded in `DEVELOPMENT.md`.

## 10. Troubleshooting

| Symptom | Action |
|---|---|
| `No module named ...` | Check the project directory, activate `.venv`, and install `requirements.lock.txt`. |
| Unsupported Python version | Create a virtual environment using Python 3.14+; changing a shell command does not change an existing environment's interpreter. |
| `GEMINI_API_KEY is not configured` | Check the root `.env`, save it and restart. Do not print or share the key. |
| `.env` changes have no effect | Exported environment variables take precedence. Unset conflicting values and restart if needed. |
| Gemini 400 | Read the sanitized error. The implementation uses `response_json_schema`; do not remove schema validation to hide the problem. |
| Gemini 401/403/404 | Check the key, project permissions and specified model access. No automatic model fallback is enabled. |
| Gemini 429 | Check rate limits/quota. Retries are bounded; do not repeatedly click Generate. |
| Docker daemon unavailable / socket error | Start Docker Desktop, wait for the engine, and run `docker info`. Do not blindly change socket permissions. |
| Runner image missing | Rebuild `ai-coder-runner:1` from the project root. |
| Invalid generated test syntax | One pre-execution regeneration is allowed. If it still fails, inspect the saved output and error; do not weaken tests to manufacture a pass. |
| Test collection error / no tests | Inspect Tests and `result.json`. Zero collected tests cannot count as a pass. |
| Preview does not open | Confirm PASSED, use the latest displayed port, check container state and inspect its logs. |
| Local port conflict | Stop duplicate instances or launch the UI with `GRADIO_SERVER_PORT=7861 python -m ai_coder.ui`. |

To inspect one identified preview container:

```sh
docker logs --tail 100 ai-coder-preview-REPLACE_WITH_ACTUAL_SUFFIX
```

## 11. Before the demo

- Start Docker Engine and build the image in advance.
- Configure `.env` locally and confirm the agreed model ID.
- Verify the AI Coder UI opens and its description/requirements are editable.
- Prepare to show MCP activity, tests, usage and downloads, not only the Randomizer page.
- Review actual generated behavior, including invalid inputs and Reset.
- Clearly label historical examples instead of presenting them as freshly generated.
- Report per-run and cumulative usage, including failed requests and unknown counts.

See [DEVELOPMENT.md](DEVELOPMENT.md) for architecture, feature boundaries, approved design adjustments and observed validation. Role instructions are in the repository's `agents/` directory.

### Reading the updated results panel

Run status appears as a colored status card; expand **Run details** for additional information. Application and Tests each use one code viewer, initially about 20 lines high. The centered **View full source** / **View full tests** control expands that same viewer; **Show less** collapses it. Copy and download always include the full content. Execution evidence has its own collapsed section.

**MCP activity** and **Usage** each have **Graphical** (default) and **JSON** subpages. Activity charts show actual call order and durations. Usage shows API attempts, known token totals, missing-metadata counts and per-agent comparisons. Unknown token counts are not zero; failed API attempts are included in usage accounting.


Reasoning marked **Not reported by Gemini** means the response omitted `usage_metadata.thoughts_token_count`, not that all usage was lost. Input, output and provider total remain independently tracked. For example, run `54e562c9f8c04960b3031b16706f99c9` recorded all five API calls and 17,315 total tokens, but none returned a separate reasoning count. Missing fields stay unknown; do not fabricate zero or add reasoning to the provider total.
