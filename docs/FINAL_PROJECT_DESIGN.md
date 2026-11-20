# AI Coder — Proposed Final Project Design

## 1. Deliverables and scope

Provider decision (2026-11-18): use the Gemini API for all three LLM-backed agents. The exact Gemini model ID remains configurable and will be verified against the group’s API access before implementation validation.

The graded system is an AI Coder: a UI accepts a software description and explicit requirements, a multi-agent system communicates through real MCP client/server calls, and the system returns executable application code and executable tests. Board Game Turn Order Randomizer is the selected generation task, not the entire AI Coder implementation.

## 2. Proposed target-application requirements

Proposed group-defined requirements are as followed:

- R1: A browser UI accepts an integer player count from 2 to 20 and exactly that many player names.
- R2: Trim leading/trailing whitespace; reject blank names, noninteger/out-of-range counts, and mismatched counts. Reject duplicate names after case-insensitive normalization with a helpful message.
- R3: Generate a uniformly shuffled permutation of the players using a standard shuffle implementation, not random-sort comparisons.
- R4: Display numbered positions 1 through N. Every player appears exactly once; never mutate or lose the submitted player list.
- R5: Allow another shuffle with the same players and allow editing/resetting the input.
- R6: Repeated orders are legitimate random outcomes; do not promise a different order every time. Random order removes a fixed positional preference but does not guarantee equal outcomes or balance every game's mechanics.
- R7: Operate without accounts or a database; do not persist personal player data by default.
- R8: Deliver runnable source, dependency instructions, a README, and executable tests.
- Tests: counts and names validation; permutation membership/length/uniqueness; input immutability; boundary cases; reshuffle behavior. Use injected/deterministic randomness for tests where appropriate; do not assert that two random draws must differ or treat a small empirical sample as proof of uniformity.

## 3. Proposed system architecture

Recommended: Python + Gradio AI Coder UI, a host orchestrator, and MCP servers exposing role-specific agent tools. The generated application can use Python/Gradio with pytest tests so the group only maintains one main programming stack.

Actual handoff:

UI -> orchestrator's MCP client -> Planner server plan_requirements(description, requirements)
-> structured spec and acceptance criteria
-> Developer server generate_application(spec)
-> application artifact manifest
-> Tester server generate_tests(spec, public_interfaces)
-> tests and coverage mapping
-> execution tool run_tests(run_id)
-> on failure, Developer server repair_application(spec, files, test_report)
-> rerun unchanged tests, at most two repair rounds
-> source ZIP, tests, execution report, usage report.

MCP tools must execute the corresponding LLM-backed role.  The host passes structured outputs between agents through MCP tools; the demo exposes the tool names, timing, status, and artifact IDs. Agent autonomy and collaboration are implemented by the application; MCP provides the client/server exchange protocol.

### Roles and boundaries

| Role | Inputs | Outputs | Access |
|---|---|---|---|
| Planner | User description and requirements | Structured spec, public interfaces, acceptance criteria | Read user request; produce plan |
| Developer | Approved run spec, failure feedback when repairing | Source files and run instructions | Write application artifacts only inside run workspace |
| Tester | Requirements and agreed public interfaces | Executable tests linked to requirements | Write test artifacts; cannot silently weaken acceptance criteria |
| Orchestrator (deterministic host, not counted as an LLM agent) | Stage results and tool status | Ordered handoffs, capped repair loop, final report | MCP clients, run state, artifact validation, usage aggregation |
| Execution tool (not an LLM agent) | Generated code/tests | Exit code and captured stdout/stderr | Isolated runner only |

For local demo, STDIO is a simple transport. Pin compatible MCP SDK dependencies and test real discovery/tool calls; write logs to stderr so they do not corrupt the protocol stream. A single server exposing all agent roles is a smaller alternative, while separate servers make the agent/tool boundaries easier to demonstrate.

## 4. UI and artifacts

Inputs: editable software description, editable numbered requirements, Gemini model configuration and API connection status, Generate button.

Outputs: stage progress; generated source viewer; tests viewer; real execution result; MCP event trace; cumulative API calls and tokens; downloadable ZIP. Include application README, requirements, source, tests, and a manifest. Provide the generated app's run command. Never substitute a prewritten randomizer for model-generated output.

Use a distinct run_id and workspace for each run. Protect artifact paths against absolute paths and traversal. Do not execute generated code in the host process with its credentials. Recommended runner: a container with network disabled, time/memory limits, restricted filesystem mounts, and no model keys. If the runner is unavailable, report NOT RUN; never fabricate a pass.

## 5. LLM usage and effectiveness

Use a shared tracked Gemini API adapter across Planner, Developer and Tester, with separate agent roles, prompts and tool permissions. Aggregate per-call events in a persistent ledger identified by run_id and agent_id. Report per-agent, per-run and cumulative API calls; input/output/reasoning counts where provided; provider total; failed attempts and unknown counts. Capture metadata before parsing structured responses. Record retries and repair requests explicitly. Missing counts are unknown, not zero. Label model calls as Gemini API calls. MCP tool calls and isolated test executions are separate counters, not LLM API calls.

Reuse the accounting approach visible in A2 as project-owned prior work, adapting it to run_id and agent_id. Do not copy A2 UI or assume current credentials/model access still work.

Use the Google GenAI SDK with a backend GEMINI_API_KEY and configurable GEMINI_MODEL. Keep the key out of source control, generated artifacts, browser responses and the execution container. No local inference server or local model weights are required. Verify the selected model’s availability and account quota before live validation; do not promise free usage or enable paid fallback automatically. Gemini API access is not an open-source-model claim.

Read usage_metadata fields prompt_token_count, candidates_token_count, thoughts_token_count (when reported), and total_token_count. Keep missing counts unknown. Include connection checks and repair calls in the ledger. If retrying a transient error, keep retries bounded and record each attempted API request; avoid hidden SDK retries that make attempt totals unverifiable. Keep the existing two-round repair limit.

Each MCP agent server calls the shared Gemini adapter for its own role. Gemini supplies generation/reasoning; MCP remains the actual communication layer used by the host to call agent tools. Sharing one Gemini model does not merge the three role-specific agents into one.

Measure first-pass test result, final test result, repair count, API calls and tokens. Report failed or partially generated runs. A fixed repair limit prevents unbounded spending or latency.

## 6. Implementation sequence

1. Confirm design and target requirements; keep the existing repository as the collaboration source.
2. Implement real MCP server/client round-trip with mock LLM adapters for deterministic protocol tests.
3. Add Planner, Developer, Tester adapters and usage accounting; validate schemas and paths.
4. Add isolated execution and capped repair flow; test timeout and failing-test paths.
5. Add AI Coder UI and downloadable artifacts; run a live model generation from the selected description.
6. Launch the generated app separately, execute its tests, and retain genuine MCP/usage evidence.
7. Prepare demo and contribution/attribution documentation.

No commits or pushes until explicitly authorized. Each member contributes using their own account and real work; do not manufacture commit history or author identities. Group can split protocol/orchestration, UI/usage, and testing/runner/docs, with cross-review. Balance is based on real contributions, not an arbitrary equal number of commits.

## 7. Acceptance and demo checklist

- Requirements are visible in the UI and discussed with the TA.
- Three distinct LLM roles execute with real MCP calls visible in logs.
- Downloaded source and tests are executable and correspond to the same run.
- Show the generated randomizer accepting players and returning a valid order.
- Show actual tests, including failure/repair when observed; distinguish mock tests from live model runs.
- Show API-call/token totals for the generation and any repairs.
- Document third-party snippets if any are adapted, including source and license; do not imply library installation is original code.
- Verify class topic registration, Canvas rubric, and scheduling separately.

## 8. Alternatives and trade-offs

A. Python/Gradio plus separate MCP agent servers (recommended): straightforward UI and tests, clear protocol evidence, more process wiring.
B. Python/Gradio plus one MCP server with three role tools: less setup, but requires clear role boundaries and transparent handoffs in the demo.
C. Custom web frontend plus backend and MCP servers: more styling control but a larger integration and testing surface than this assignment needs initially.

Reference: MCP architecture https://modelcontextprotocol.io/docs/learn/architecture (host/client/server, tools and transports). Specific SDK API/version will be verified during implementation.

## 9. Implementation clarification — 2026-11-19

The user approved one Tester regeneration for Python syntax errors before the first execution. The host supplies the error and rejected tests, retains the original attempt, and stops if the regenerated tests are still invalid. Tests cannot change after execution starts or during Developer repair. This adds a bounded pre-execution generation step without changing the three-role architecture. See DEVELOPMENT.md for implementation and measured validation status.
