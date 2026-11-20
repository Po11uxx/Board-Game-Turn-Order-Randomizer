import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class Ledger:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event):
        event['time'] = datetime.now(timezone.utc).isoformat()
        # One O_APPEND write per event; role processes never rewrite the ledger.
        data = (json.dumps(event) + '\n').encode()
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, data)
        finally:
            os.close(fd)

    def start(self, run_id, agent_id, purpose, model):
        call_id = uuid4().hex
        self.append(dict(event='start', call_id=call_id, run_id=run_id,
                         agent_id=agent_id, purpose=purpose, model=model))
        return call_id

    def finish(self, call_id, status, usage=None, duration=0):
        self.append(dict(event='finish', call_id=call_id, status=status,
                         usage=usage, duration=duration))

    def calls(self, run_id=None):
        calls = {}
        if not self.path.exists():
            return []
        for line in self.path.read_text().splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue  # An interrupted last write remains an unknown attempt.
            if event['event'] == 'start':
                calls[event['call_id']] = event
            elif event['call_id'] in calls:
                calls[event['call_id']].update(event)
        return [c for c in calls.values() if run_id is None or c['run_id'] == run_id]

    def summary(self, run_id=None, agent_id=None):
        calls = [c for c in self.calls(run_id) if agent_id is None or c['agent_id'] == agent_id]
        fields = {'input_tokens': 'prompt_token_count', 'output_tokens': 'candidates_token_count',
                  'reasoning_tokens': 'thoughts_token_count', 'provider_total_tokens': 'total_token_count'}
        result = {'api_calls': len(calls), 'failed_calls': sum(c.get('status') == 'error' for c in calls),
                  'unknown_usage_calls': sum((c.get('usage') or {}).get('total_token_count') is None for c in calls)}
        for label, field in fields.items():
            values = [(c.get('usage') or {}).get(field) for c in calls]
            result[label] = sum(v for v in values if v is not None)
            result[label + '_unknown_calls'] = sum(v is None for v in values)
        return result
