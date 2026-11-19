# AI Coder Figma Prototype

Created from the revised `FINAL_PROJECT_DESIGN.md` for SWE-265P-Spring-2026.

- [Editable Figma design](https://www.figma.com/design/IrmB4yvO28wJImQZK6F7Pb?node-id=4-129)
- [AI Coder prototype start](https://www.figma.com/proto/IrmB4yvO28wJImQZK6F7Pb?node-id=4-129&starting-point-node-id=4%3A129)
- [Generated randomizer prototype start](https://www.figma.com/proto/IrmB4yvO28wJImQZK6F7Pb?node-id=6-477&starting-point-node-id=6%3A477)

## Scope

19 editable desktop screen states, each 1280 × 960. Screens use auto-layout, reusable component instances, bound color/spacing/radius tokens, DM Sans typography, warm neutral surfaces, forest-green actions, amber exception states and lilac usage notes. Button instances are based on Figma's Simple Design System library.

This is an interactive design prototype, not an implemented AI Coder or executable game. Values, code excerpts, test results and tokens are illustrative and marked as sample data. Navigation is implemented with Figma click reactions. Text fields demonstrate prepared states rather than accepting arbitrary typed input. Shuffle results are prepared examples, not live randomness. Download actions show confirmation views, not real ZIP downloads.

## Main walkthrough

1. Start at **From idea to working software**.
2. Review the project description and R1–R8 requirements.
3. Click **Review configuration**, then **Generate application**.
4. View Planner, Developer, Tester and Execution stages.
5. Click **View test outcome** to inspect the failing test and first repair.
6. Click **View repaired result** to reach the successful source view.
7. Explore **Tests**, **MCP activity**, and **Token usage** tabs.
8. Open the application preview or view the project download confirmation.

## Generated application walkthrough

1. **Who is playing?** shows a prepared four-player table.
2. **See validation example** shows case-insensitive duplicate-name rejection; **Correct duplicate name** returns to the valid form.
3. **Randomize turn order** opens a numbered result with each player present once.
4. **Shuffle again** shows an alternate prepared order. Copy explains that repeated outcomes are also valid.
5. **Edit players** returns to the input form; **Reset** opens an empty state.
6. Click an empty field or **Load example players** to restore the sample table.

## Exceptional paths

- **Check validation** on the brief page shows missing description/requirements before any model call.
- **Runner unavailable** from generation shows **NOT RUN**, never a passing result.
- **Repair limit reached** from repair shows the stopped state after two rounds.
- Those branches lead to **Generated files · not verified** and the unverified bundle confirmation, preserving their incomplete verification status.

## Screen inventory

| State | Figma node |
|---|---|
| Project brief | 4:129 |
| Model configuration | 4:203 |
| Agent generation | 4:267 |
| Failure / repair | 4:351 |
| Verified source | 5:113 |
| Tests and coverage | 5:201 |
| MCP trace | 5:292 |
| Token usage | 5:380 |
| Verified bundle confirmation | 5:472 |
| Runner unavailable | 6:292 |
| Repair limit reached | 6:356 |
| Brief validation | 6:422 |
| Player inputs | 6:477 |
| Duplicate-name validation | 6:528 |
| Empty/reset input | 6:574 |
| First sample order | 6:620 |
| Second sample order | 6:665 |
| Unverified source | 8:460 |
| Unverified bundle confirmation | 8:511 |

## Validation

- All 19 screens are reachable from the AI Coder starting point.
- Screen-boundary checks found no text outside the 1280 × 960 viewports after layout fixes.
- Hotspots were checked against their intended destinations, including exception branches and clearing inherited library reactions.
- Visual screenshots reviewed for the main workflow and game states.
- This verifies the Figma structure and links; it does not verify real model generation, MCP transport, code execution, fairness of an implementation, or actual file downloads.

## Provider decision — 2026-11-18

The group selected Gemini API. Provider configuration should show Gemini API, a configurable Gemini model ID and backend credential status. All model-call metrics should read Gemini API calls. The MCP transport and isolated test runner remain separate from the model provider. No localhost inference endpoint or local model installation is required. Prototype figures remain illustrative.
