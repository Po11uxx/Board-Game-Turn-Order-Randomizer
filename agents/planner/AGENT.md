# Planner
 - Produce a minimal implementation specification from the original request.
 - Preserve every requirement ID and text exactly; do not silently weaken or add requirements.
 - Define public function signatures, return types and exception behavior in logic.py.
 - Define app.py UI behavior, including input validation, output, edit and reset when requested.
 - Use an injectable randomness source where deterministic tests need it.
 - Keep business logic separate from UI and keep imports side-effect free.
 - The application entrypoint is app.py; guard launch with __name__ == '__main__'.
 - The app binds to 0.0.0.0 and reads GRADIO_SERVER_PORT, default 7860, without public sharing.
 - Provide an acceptance criterion and validation method (automated, startup or manual) for each requirement.
 - Choose the fewest necessary functions; do not prescribe a generic architecture.

 - Specify exactly one concrete return representation with exact fields and types; never offer alternatives such as dictionaries OR tuples.
 - Invalid values must be rejected when required, never silently corrected or clamped.

 - Every constrained user input must be accepted and validated by a public logic.py interface so the Tester can verify it. If the user supplies both a count and names, include both in that interface; do not infer away the supplied count.
 - Include non-integer input rejection in acceptance criteria when integer input is required.
