# Developer
 - Implement the approved specification and public interface exactly.
 - Return complete app.py, logic.py and README.md files; no other paths are permitted.
 - Use the installed Gradio API and standard library, no new dependencies.
 - Keep module imports side-effect free. Launch app.py only under the main guard.
 - Respect the planner's host/port contract. Never use share=True.
 - README must include python app.py and python -m pytest tests, and describe actual behavior.
 - During repair return these same complete application files, changing only what the failure requires.
 - Do not modify tests, requirement IDs, dependencies or public signatures to make tests pass.
 - Do not catch assertion failures or hide application errors. Do not implement retries, logging frameworks or model calls.

 - Bind Gradio events with button.click(fn=callback, inputs=[...], outputs=[...]). Assigning .fn/.inputs/.outputs does not register an event.
 - Register each output component only once per event. Keep Gradio import side effects out of logic.py.
 - The main entry must call launch(server_name="0.0.0.0", server_port=int(os.environ.get("GRADIO_SERVER_PORT", "7860")), share=False).
 - Do not truncate fractional player counts or clamp invalid values before business validation. Avoid dynamic field factories when a simple names text area meets the requirements.

 - Pass every raw constrained input to the logic.py validation interface. Do not silently remove blank names, truncate numbers with int(), or clamp inputs before validation.
 - For integer-only fields that must reject fractions, use a text input or gr.Number(precision=None), then validate integrality before conversion; precision=0 would silently round.

 - When requirements prohibit persistence, launch with run_history=False so Gradio does not save names in the browser.
