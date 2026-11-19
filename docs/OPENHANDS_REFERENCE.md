# OpenHands reference and attribution plan

Reviewed: 2026-11-18. Scope: official repository READMEs and root LICENSE files; no source implementation has been audited, installed, copied or adapted during this review.

## Verified references

- [OpenHands/OpenHands](https://github.com/OpenHands/OpenHands): the current README describes Agent Canvas, a self-hosted interface for coding agents and multiple execution backends. Its agent compatibility description includes ACP; this does not establish that our course-required MCP handoffs are implemented.
- [OpenHands/software-agent-sdk](https://github.com/OpenHands/software-agent-sdk): the current README identifies this as the SDK/Agent Server implementation, covering agents, tools, conversations, workspaces and events. This is the more relevant starting point for backend design research. Its examples/documentation include MCP topics, but individual examples have not yet been inspected or validated for this project.
- [Canvas root license](https://github.com/OpenHands/OpenHands/blob/main/LICENSE) and [SDK root license](https://github.com/OpenHands/software-agent-sdk/blob/main/LICENSE): currently MIT. Check the exact version and relevant file notices before copying anything; preserve applicable copyright and license notices when distributing copied/substantial portions.

These links track main and may change. Before any actual reuse, record a pinned commit and immutable file URLs.

## Proposed application to our project

These mappings are our recommendations, not claims that OpenHands implements our exact course workflow.

| Reference concept | Our scoped application |
|---|---|
| Separate agent responsibilities from execution tools | Planner, Developer and Tester remain distinct from the deterministic orchestrator and runner |
| Separate UI from agent backend | Keep the current prototype; expose stage progress, code, tests and execution evidence |
| Workspace-based execution | Use a separate run workspace and a restricted runner for generated code |
| Configurable LLM and tool access | Configure an available model/provider; limit each agent to its required tools |
| Events and conversation state | Retain a run-specific MCP event trace and artifact references |

Retain our explicit requirements-to-tests mapping, real MCP client/server calls, fixed repair limit, unchanged tests during repair, and per-agent/per-run/cumulative usage accounting. These are project requirements/design decisions, not attributed OpenHands features from this limited review.

## Use categories

1. Conceptual inspiration: cite the relevant documentation in the design/report, and state that implementation was written independently.
2. Package dependency: record the package/version/license and explain which capabilities it supplies; do not describe dependency internals as group-authored work.
3. Copied or modified code, prompts, configurations, or tests: record the upstream commit, exact source file/section, local destination, modifications, and applicable notices. Add a source comment near adapted code and maintain a central attribution record.

Suggested attribution record fields:

- Reference name and repository
- Pinned commit/tag and immutable source-file URL
- Original lines, function, or section
- Local file and function
- Copied unchanged / modified / dependency only / conceptual inspiration
- Specific changes made by the group
- License and retained notice location

Do not create a filled adaptation record until actual reuse occurs. Current status for OpenHands: reference-only; no copied or adapted implementation code.

## Model choice

Decision updated 2026-11-18: the group selected Gemini API. Use a shared tracked Gemini adapter with role-specific prompts and a configurable model ID. Do not inherit a different provider/model from the OpenHands quickstart. No local model installation is planned. Verify API access and quota before live testing; do not assume free usage or describe Gemini as open-source. Missing usage counts remain unknown.

## Presentation wording

Use only if still accurate at submission:

“We consulted OpenHands as an architectural reference for separating agents, tools, workspaces and the user interface. Our implementation and any dependencies or adapted sections are identified in the repository. The Planner–Developer–Tester MCP workflow and requirements-specific evaluation are explained separately.”

Update this statement if implementation later incorporates OpenHands code or SDK packages. Do not present reference-only status as permanent.
