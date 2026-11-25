# Project team (name and student ID)
# 项目组成员（姓名与学号）
# Ping Lu 40881056
# xiyao Li 50205246
# Xinyi Xu 78287646

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class Ledger:
    # Store the usage ledger path and ensure its parent directory exists.
    # 保存用量日志路径，并确保父目录存在。
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    # Append one timestamped JSON event so MCP processes can share a single usage log.
    # 逐条追加带时间戳的 JSON 事件，让多个 MCP 进程共用一份用量日志。
    def append(self, event):
        event['time'] = datetime.now(timezone.utc).isoformat()
        # One O_APPEND write per event; role processes never rewrite the ledger.
        # 每条事件通过 O_APPEND 模式写入一次，各角色进程不重写日志。
        data = (json.dumps(event) + '\n').encode()
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, data)
        finally:
            os.close(fd)

    # Record an API attempt and return the ID used to match its outcome.
    # 记录一次 API 请求，并返回用于关联请求结果的编号。
    def start(self, run_id, agent_id, purpose, model):
        call_id = uuid4().hex
        self.append(dict(event='start', call_id=call_id, run_id=run_id,
                         agent_id=agent_id, purpose=purpose, model=model))
        return call_id

    # Record the outcome, duration, and available token metadata for an API attempt.
    # 保存这次 API 请求的结果、耗时和可用的 token 数据。
    def finish(self, call_id, status, usage=None, duration=0, *, error_code=None, retry_delay=None):
        self.append(dict(event='finish', call_id=call_id, status=status,
                         usage=usage, duration=duration, error_code=error_code, retry_delay=retry_delay))

    # Combine start and finish records while retaining attempts that lack a completion record.
    # 合并请求的开始和结束记录，同时保留没有结束记录的请求。
    def calls(self, run_id=None):
        calls = {}
        if not self.path.exists():
            return []
        for line in self.path.read_text().splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue  # An interrupted last write remains an unknown attempt.
                # 末尾记录写入中断时，对应请求的用量保持为未知。
            if event['event'] == 'start':
                calls[event['call_id']] = event
            elif event['call_id'] in calls:
                calls[event['call_id']].update(event)
        return [c for c in calls.values() if run_id is None or c['run_id'] == run_id]

    # Count attempts and aggregate known token values by run or role while tracking missing data.
    # 按运行或角色统计请求次数、汇总已知 token 数量，并跟踪缺失数据。
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
