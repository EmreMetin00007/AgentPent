"""AgentPent — KaliTerminalTool Tests."""

import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.mission import Mission
from core.orchestrator import Orchestrator
from tools.kali_terminal import KaliTerminalTool


class TestKaliTerminalTool:

    def setup_method(self):
        self.tool = KaliTerminalTool()
        self.orch = Orchestrator()
        self.mission = self.orch.create_mission("Test", ["10.10.10.5", "example.com"])

    def test_metadata(self):
        assert self.tool.name == "kaliterminal"
        assert self.tool.timeout == 120
        assert "terminal" in self.tool.description

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_shell")
    async def test_execute_success(self, mock_shell):
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"uid=0(root) gid=0(root) groups=0(root)", b"")
        mock_proc.returncode = 0
        mock_shell.return_value = mock_proc

        result = await self.tool.execute({"command": "id", "target": "10.10.10.5"})
        assert result.success
        assert "uid=0(root)" in result.stdout

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_shell")
    async def test_execute_failure(self, mock_shell):
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"command not found")
        mock_proc.returncode = 127
        mock_shell.return_value = mock_proc

        result = await self.tool.execute({"command": "invalid_cmd", "target": "10.10.10.5"})
        assert not result.success
        assert result.return_code == 127
        assert "command not found" in result.stderr

    @pytest.mark.asyncio
    async def test_scope_guard(self):
        # BaseTool handles scope check against explicit target argument in params
        result = await self.tool.execute({"command": "ping -c 1 8.8.8.8", "target": "8.8.8.8"})
        assert not result.success
        assert "kapsam" in result.error.lower()

    def test_parse_output(self):
        result = self.tool.parse_output("drwxr-xr-x 2 root root 4096 /etc")
        assert "raw_terminal_output" in result
        assert "/etc" in result["raw_terminal_output"]

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_shell")
    async def test_execute_timeout(self, mock_shell):
        mock_proc = AsyncMock()

        async def slow_communicate():
            await asyncio.sleep(0.5)
            return (b"", b"")

        mock_proc.communicate = slow_communicate
        mock_shell.return_value = mock_proc

        self.tool.timeout = 0.1  # Hızlı timeout

        result = await self.tool.execute({"command": "sleep 10", "target": "10.10.10.5"})
        assert not result.success
        assert "timed out after" in result.error

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_shell")
    async def test_truncation(self, mock_shell):
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"A" * 20000, b"")
        mock_proc.returncode = 0
        mock_shell.return_value = mock_proc

        result = await self.tool.execute({"command": "cat /huge_file", "target": "10.10.10.5"})
        assert result.success
        assert len(result.stdout) < 20000
        assert "[TRUNCATED:" in result.stdout
