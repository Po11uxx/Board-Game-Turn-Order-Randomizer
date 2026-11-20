import asyncio
import json
import os
import time
from pathlib import Path
from pydantic import ValidationError
from google import genai
from google.genai import errors, types

ROOT = Path(__file__).resolve().parents[1]
ROLES = ('planner', 'developer', 'tester')
DEFAULT_MODEL = 'gemini-3.5-flash-lite'


def instructions(role):
    if role not in ROLES:
        raise ValueError('Unknown agent role')
    return '\n\n'.join((ROOT / p).read_text() for p in ('agents/COMMON.md', f'agents/{role}/AGENT.md'))


class Gemini:
    def __init__(self, ledger, client=None):
        self.ledger = ledger
        self.model = os.environ.get('GEMINI_MODEL', DEFAULT_MODEL)
        self.client = client

    async def generate(self, run_id, role, purpose, payload, schema):
        if self.client is None:
            key = os.environ.get('GEMINI_API_KEY')
            if not key:
                raise ValueError('GEMINI_API_KEY is not configured in the backend')
            self.client = genai.Client(api_key=key, http_options=types.HttpOptions(
                api_version='v1beta', timeout=120000,
                retry_options=types.HttpRetryOptions(attempts=1)))
        prompt = json.dumps(payload)
        for attempt in range(2):
            call_id = self.ledger.start(run_id, role, purpose, self.model)
            started = time.monotonic()
            try:
                response = await self.client.aio.models.generate_content(
                    model=self.model, contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=instructions(role),
                        response_mime_type='application/json', response_json_schema=schema.model_json_schema(),
                        temperature=0.2, max_output_tokens=16000))
            except Exception as exc:
                # The API boundary owns accounting. Do not log exception bodies/keys.
                self.ledger.finish(call_id, 'error', duration=time.monotonic() - started)
                if isinstance(exc, errors.APIError) and exc.code in (429, 500, 502, 503, 504) and attempt == 0:
                    await asyncio.sleep(2)
                    continue
                code = getattr(exc, 'code', None)
                message = str(getattr(exc, 'message', ''))
                message = message.replace(os.environ.get('GEMINI_API_KEY') or '<unset>', '[REDACTED]')[:1500]
                raise RuntimeError(f'Gemini request failed ({type(exc).__name__}, code={code}): {message}; no fallback model used') from None
            usage = response.usage_metadata
            self.ledger.finish(call_id, 'ok', usage.model_dump(exclude_none=True) if usage else None,
                               time.monotonic() - started)
            # Persist usage even when structured output is incomplete or invalid.
            try:
                return schema.model_validate_json(response.text or '')
            except ValidationError as exc:
                if attempt == 1:
                    raise ValueError('Gemini returned invalid structured output after two attempts') from None
                prompt += '\nYour previous response did not validate. Return only this role output matching the schema. Errors: ' + json.dumps(exc.errors(include_url=False, include_context=False, include_input=False))[:2000]

    async def close(self):
        if self.client:
            await self.client.aio.aclose()
