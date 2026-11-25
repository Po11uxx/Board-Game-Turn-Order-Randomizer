# Developer
 - Implement the approved specification and public interface exactly.
 - Export every function in spec.ui_callbacks from app.py using its agreed name and signature, and bind it to the specified event.
 - Return complete app.py, logic.py and README.md files; no other paths are permitted.
 - Use the installed Gradio API and standard library, no new dependencies.
 - Importing app.py must return without starting Gradio. Put demo.launch(...) inside the exact guard `if __name__ == "__main__":`. Do not add an unconditional branch or an `or` condition to the guard.
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
 - Gradio passes values for all components bound to a callback, including hidden ones. In the app.py callback only, pass the first N field values to business validation once the count is known to be valid. Preserve blanks among those active fields.
 - When the business function requires exactly N names, logic.py must reject both shorter and longer lists. It must never slice or filter the incoming list to make its length pass validation. Check both boundaries when repairing count/name mismatches.
 - For integer-only fields that must reject fractions, use a text input or gr.Number(precision=None), then validate integrality before conversion; precision=0 would silently round.

 - When requirements prohibit persistence, pass run_history=False to demo.launch(...). Gradio's gr.Blocks(...) constructor does not accept run_history.
