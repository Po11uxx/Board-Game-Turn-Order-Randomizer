# Live MCP Activity and Generation Validation

November 20, 2026 · Board Game Turn Order Randomizer

AI Coder now displays MCP tool calls during generation and validates the interface shared by the generated application and its tests. Two consecutive runs submitted through the updated Gradio generation endpoint passed all generated tests and the Docker startup check.

## What changed

- **Live activity.** The MCP activity tab updates both the graphical view and the JSON view when a tool starts and when it finishes. Each entry shows the agent, tool, and status (`running`, `ok`, or `error`). Completed calls include their elapsed time.
- **Consistent trace.** The orchestrator saves each trace update and sends a snapshot to the UI. The final trace uses the same tool calls that appeared during generation.
- **Hidden name fields.** Gradio sends all bound name fields to the Randomize callback, including hidden ones. For N players, the callback selects the first N fields and preserves any blanks among them. The business function still rejects both shorter and longer lists. A generated test exercises the callback with four active names and hidden fields. [Default requirements](../ai_coder/ui.py) · [Developer instructions](../agents/developer/AGENT.md)
- **Shared callback contract.** The Planner declares the public UI callbacks. The orchestrator checks the Tester’s imports against that list and allows one regeneration before execution when tests have invalid syntax or import undeclared callbacks. Developer repairs continue to use the selected tests without changing them. [Planner instructions](../agents/planner/AGENT.md) · [Orchestrator](../ai_coder/orchestrator.py)
- **Docker import check.** Before pytest, the runner imports the application and verifies the callbacks used by the tests. Application import failures and the 15-second import timeout can trigger Developer repair. The runner reports a pytest timeout separately. The Developer instructions also specify the Gradio main guard and put `run_history=False` on `launch()`. [Runner](../runtime/entry.py) · [Developer instructions](../agents/developer/AGENT.md)

## Verification

| Check | Result |
| --- | --- |
| Project test suite | 42 passed, including live trace streaming, undeclared callback regeneration, and application import checks. |
| First live run, `6d6a30b49305439abcc42eac957e58ab` | 8 of 8 generated tests passed and Docker startup succeeded. |
| Second live run, `e6c6d86eaa314f31a74f0fa1992b2278` | 7 of 7 generated tests passed and Docker startup succeeded. |
| Preview regression | Both generated Randomize endpoints returned four numbered entries containing four Chinese test names exactly once. Sixteen hidden fields were ignored, and a blank active name produced an error. |
| Replayed failures | The original undeclared callback imports were rejected before pytest. The original app that launched Gradio on import reproduced the 15-second import timeout and was marked repairable. |

The run IDs identify local `runs/` evidence. Each successful run can export a ZIP containing the generated application, tests, reports, trace, and usage summary.

## Running the updated version

Rebuild the Docker image after switching to the updated branch so the import checks run inside the container. Activate the project's Python environment and start the platform. [Full setup guide](RUN_GUIDE_EN.md)

```bash
docker build -t ai-coder-runner:1 runtime
source .venv/bin/activate
python -m ai_coder.ui
```

Use **Generate application** with the default requirements and watch **MCP activity**. After the run shows **PASSED**, select **Open isolated preview** and follow the generated app link.

## Gemini 503 diagnosis

Earlier live runs stopped at different stages: planning, application generation, and test generation. Each terminal error was Gemini HTTP `503`, with a message that the model was experiencing high demand. Google describes this response as temporary service overload. [Google Gemini API guidance](https://discuss.ai.google.dev/t/handling-429-503-errors-from-the-gemini-api/124640)

An earlier successful run, `978d51f38821497896b909928e6ac50c`, recorded one failed repair-stage API attempt, followed by a successful retry. The usage ledger does not retain the HTTP status of that attempt.
