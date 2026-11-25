# Project team (name and student ID)
# 项目组成员（姓名与学号）
# Ping Lu 40881056
# xiyao Li 50205246
# Xinyi Xu 78287646

import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4
from ai_coder.models import Execution

IMAGE = 'ai-coder-runner:1'


# Run a Docker CLI command with captured output and a deadline.
# 执行 Docker 命令，收集输出并限制执行时间。
def docker(*args, timeout=15):
    return subprocess.run(['docker', *args], capture_output=True, text=True, timeout=timeout)


class DockerRunner:
    # Check the Docker CLI, daemon, and runner image before spending model calls.
    # 在调用模型前确认 Docker 命令行、守护进程和执行镜像可用。
    def check(self):
        if not shutil.which('docker'):
            return 'Docker CLI is not installed'
        try:
            if docker('info', '--format', '{{.ServerVersion}}').returncode:
                return 'Docker daemon is unavailable. Start Docker Desktop.'
            if docker('image', 'inspect', IMAGE).returncode:
                return 'Runner image missing. Run: docker build -t ai-coder-runner:1 runtime'
        except subprocess.TimeoutExpired:
            return 'Docker health check timed out'
        return None

    # Build the shared container limits and mount generated source read-only.
    # 设置共用的容器限制，并以只读方式挂载生成源码。
    @staticmethod
    def restrictions(root):
        return ['--env=GRADIO_RUN_HISTORY=False', '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                '--memory=768m', '--cpus=1', '--pids-limit=128',
                '--tmpfs=/tmp:rw,nosuid,size=128m,mode=1777',
                '--log-driver=local', '--log-opt=max-size=1m', '--log-opt=max-file=1', '--log-opt=compress=false',
                '--mount', f'type=bind,source={root.resolve()},target=/workspace,readonly']

    # Execute tests and the startup check in a network-disabled container and collect its final report.
    # 在禁用网络的容器中执行测试和启动检查，并收集最终报告。
    def run(self, root: Path):
        problem = self.check()
        if problem:
            return Execution(status='NOT RUN', detail=problem)
        name = 'ai-coder-test-' + uuid4().hex
        try:
            start = docker('run', '-d', '--name', name, '--network=none', *self.restrictions(root), IMAGE)
            if start.returncode:
                return Execution(status='ERROR', detail=start.stderr[-2000:])
            wait = docker('wait', name, timeout=110)
            if wait.returncode:
                return Execution(status='ERROR', detail=wait.stderr[-2000:])
            logs = docker('logs', '--tail', '1', name)
            if logs.returncode or not logs.stdout.strip() or len(logs.stdout.encode()) > 64000:
                return Execution(status='ERROR', detail='Runner did not return a valid bounded report: ' + logs.stderr[-2000:])
            return Execution.model_validate_json(logs.stdout)
        except subprocess.TimeoutExpired:
            return Execution(status='ERROR', detail='Runner timed out; container terminated')
        finally:
            self._remove(name)

    @staticmethod
    def _remove(name):
        # Cleanup must not replace the original execution/startup failure.
        try:
            docker('rm', '-f', name)
        except (OSError, subprocess.TimeoutExpired):
            pass

    # Start a preview container and resolve the port published on localhost.
    # 启动预览容器，并查询映射到本机的端口。
    def preview(self, root: Path):
        problem = self.check()
        if problem:
            raise RuntimeError(problem)
        # User-approved demo trade-off: preview may access the network, but
        # 按用户确认的演示配置，预览容器可以访问网络。
        # only a localhost port is published and backend keys are not inherited.
        # 端口只发布到本机，容器也不会继承后端密钥。
        network = 'bridge'
        name = 'ai-coder-preview-' + uuid4().hex
        try:
            result = docker('run', '-d', '--name', name, '--network', network,
                           '-p', '127.0.0.1::7860', *self.restrictions(root), IMAGE,
                           'python', 'app.py')
            if result.returncode:
                raise RuntimeError('Preview container could not start: ' + result.stderr[-2000:])
            mapping = docker('port', name, '7860/tcp').stdout.strip()
            if not mapping.startswith('127.0.0.1:') or not mapping.removeprefix('127.0.0.1:').isdigit():
                raise RuntimeError('Preview did not expose a localhost port')
            url = 'http://' + mapping
            # Ignore proxy environment variables for this localhost-only probe.
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                state = docker('inspect', '--format', '{{.State.Running}}', name)
                if state.returncode or state.stdout.strip() != 'true':
                    break
                try:
                    with opener.open(url, timeout=1) as response:
                        if response.status == 200:
                            return name, url
                except (urllib.error.URLError, TimeoutError, OSError):
                    pass
                time.sleep(0.5)
            logs = docker('logs', '--tail', '40', name)
            raise RuntimeError('Preview failed to become ready within 30 seconds or exited.\n'
                               + (logs.stdout + logs.stderr)[-4000:])
        except BaseException:
            self._remove(name)
            raise

    # Remove a preview container whose name belongs to this application.
    # 根据容器名称移除本应用创建的预览容器。
    def stop_preview(self, name):
        if name and name.startswith('ai-coder-preview-'):
            self._remove(name)
