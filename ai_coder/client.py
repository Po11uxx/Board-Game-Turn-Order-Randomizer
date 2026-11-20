import json
import os
import sys
from contextlib import AsyncExitStack
from datetime import timedelta
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from ai_coder.gemini import ROOT, ROLES


class AgentClients:
    def __init__(self, runs: Path):
        self.runs = runs.resolve()
        self.sessions = {}
        self.stack = AsyncExitStack()

    async def __aenter__(self):
        try:
            for role in ROLES:
                env = {k: os.environ[k] for k in ('PATH', 'HOME', 'GEMINI_API_KEY', 'GEMINI_MODEL') if k in os.environ}
                env['PYTHONPATH'] = str(ROOT)
                params = StdioServerParameters(command=sys.executable,
                    args=['-m', 'ai_coder.server', '--role', role, '--ledger', str(self.runs / 'usage.jsonl')],
                    env=env, cwd=str(ROOT))
                read, write = await self.stack.enter_async_context(stdio_client(params))
                session = await self.stack.enter_async_context(ClientSession(read, write, read_timeout_seconds=timedelta(seconds=300)))
                await session.initialize()
                self.sessions[role] = session
        except BaseException:
            await self.stack.aclose()
            raise
        return self

    async def __aexit__(self, *args):
        await self.stack.aclose()

    async def tools(self, role):
        return {tool.name for tool in (await self.sessions[role].list_tools()).tools}

    async def call(self, role, name, arguments):
        result = await self.sessions[role].call_tool(name, arguments)
        if result.isError:
            detail = '\n'.join(c.text for c in result.content if c.type == 'text')
            # Server errors are sanitized by the Gemini adapter.
            raise RuntimeError(f'{name}: {detail[:2000]}')
        if result.structuredContent is not None:
            return result.structuredContent
        return json.loads(next(c.text for c in result.content if c.type == 'text'))
