# Recovery state machine

| State | Behavior and available actions |
| --- | --- |
| Ready | Description and requirements are editable. Generate application starts a run. |
| Running | Inputs and Generate are disabled. Run status and MCP activity show progress. Preview, empty download and recovery actions are hidden. No Gradio loading bars or outlines. |
| Waiting for Gemini | The same run waits before another API attempt. Status reports the HTTP code and backoff. No fallback model is selected. |
| Passed | Inputs become editable. Open isolated preview and Download project are available. Generate again starts a separate run. |
| Failed | Application verification failed after bounded repair. Show verification evidence, Edit inputs, Generate again and available diagnostics. Preview stays hidden. |
| Error | Agent/API/infrastructure error ends the run. Show the cause and next steps; restore editable inputs and Generate again. A 503 suggests waiting before generating again. Available artifacts are diagnostics, not a verified project. |
| Not run | Explain the runner prerequisite problem. Restore inputs and Generate again; preview stays hidden. |
| Preview error | Preserve the passed generation result and show the preview error. Open isolated preview remains available for another attempt after checking Docker. |

## Three distinct recovery mechanisms

1. Provider requests: at most four API attempts per agent invocation. HTTP 429, 500, 502, 503 and 504 receive exponential backoff (5, 10, 20 seconds plus 0–1 second jitter). Invalid structured output receives at most one correction within the same four-attempt budget. Other API errors stop immediately. The SDK does not add hidden retries. The MCP timeout is 540 seconds, covering four 120-second requests and backoff.
2. Application repair: failing verification can send evidence to Developer for at most two repair rounds. Executed tests remain locked. Reaching final FAILED stops automatic repair.
3. User restart: the existing generation button becomes Generate again. This creates a new run with a new ID and additional usage; it does not resume the previous run or silently alter its tests. No separate Retry button or automatic full-pipeline restart is added.

Every API attempt, including failed retries, is logged. Error code and scheduled backoff are retained; unavailable token metadata remains unknown rather than zero. Temporary provider overload cannot be resolved by local code, so exhausted retries end in an actionable ERROR.

## Verification scope

Regression tests simulate temporary 503 recovery and exhaustion, check attempt accounting, and verify running/terminal control states. These checks do not prove that the live Gemini service has recovered.
