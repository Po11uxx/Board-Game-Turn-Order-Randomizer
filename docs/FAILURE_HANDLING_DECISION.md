# Decision: bounded failure handling and behavior-based tests

Date: 2026-11-20

## Observed failure

Run `d740a16b0ae14a0684adb0f321ebf261` ended in **FAILED** after the allowed two Developer repairs. The final execution had five passing tests and one failing test. The duplicate-name test used:

```python
with pytest.raises(ValueError, match="duplicate"):
    ...
```

The application raised `ValueError` with `Duplicate player name found: 'alice' (case-insensitive).` The case-sensitive regular expression did not match the capitalized word. The input was rejected, but the test imposed a capitalization requirement not established by the user requirements. Earlier failures similarly depended on exact phrases. The second repair left the application logic unchanged, so the remaining assertion still failed.

This diagnosis explains this particular failure; it does not establish that the generated application meets every requirement.

## Why not add a Retry button?

The existing **Generate application** action already starts a fresh run with the current description and requirements. A second button with the same behavior would duplicate that action and could misleadingly imply that it resumes the old run or guarantees recovery.

Repeated model calls do not address an unnecessarily strict test contract. Unlimited retries would increase token usage, reduce demo predictability and undermine the approved two-repair limit. Failures should remain visible and explainable.

Decision: keep the existing generation action and bounded recovery. A new generation creates a new run ID, preserves the prior on-disk evidence and records all additional API attempts/tokens. No independent Retry button or automatic restart was added.

## Tester rule change

The Tester instructions now require:

- Validate the agreed error mechanism and rejection behavior, including required exception types or error-return structure.
- Do not invent exact sentences, capitalization or punctuation unless specified by the requirements or agreed interface.
- If helpful error text is required, check that it is non-empty. Require semantic keywords only when the contract actually specifies them; use case-insensitive comparison when case is not specified.
- Retain exact-text assertions when exact text is explicitly required.
- Preserve invalid-input boundaries and other behavioral checks. This is not permission to weaken tests to accommodate broken code.

For example, where the contract requires `ValueError` and a helpful message but no exact wording:

```python
with pytest.raises(ValueError) as exc_info:
    validate_players(2, ["Alice", "alice"])  # Illustrative public interface.
assert str(exc_info.value).strip()
```

The function name above is illustrative; generated tests must use the Planner's actual agreed interface.

## Test immutability and validation limits

The instruction change applies to future test generation. Existing failed-run source and locked tests were not edited, and the failed result was not relabeled as passing. Tests remain immutable after execution starts; only the previously approved one-time pre-execution syntax regeneration is permitted.

This update changes the prompt policy, not a deterministic guarantee about future model output. The rule text has been reviewed; no new Gemini generation was made solely to validate this adjustment. Offline regression results are recorded separately in the development record.
