"""AgentPent — SQLMap & FFUF Tool Unit Tests."""

import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from tools.sqlmap_tool import SQLMapTool
from tools.ffuf_tool import FFUFTool


# ── SQLMap Tests ─────────────────────────────────────────

SQLMAP_OUTPUT = """
[*] starting at 12:00:00

[12:00:01] [INFO] testing connection to the target URL
[12:00:02] [INFO] testing if the target URL content is stable

Parameter: username (GET)
    Type: boolean-based blind (AND boolean-based)

Parameter: id (GET)
    Type: UNION query (UNION-based)

[12:00:10] [INFO] the back-end DBMS is MySQL
web application technology: Apache 2.4.54, PHP 8.1.12
back-end DBMS: MySQL >= 5.6

available databases [3]:
[*] information_schema
[*] myapp_db
[*] mysql
"""

FFUF_JSON_OUTPUT = json.dumps({
    "commandline": "ffuf -u http://target/FUZZ -w common.txt",
    "results": [
        {
            "input": {"FUZZ": "admin"},
            "url": "http://target/admin",
            "status": 200,
            "length": 4521,
            "words": 312,
            "lines": 75,
            "content-type": "text/html",
            "redirectlocation": "",
            "duration": 45,
        },
        {
            "input": {"FUZZ": "backup"},
            "url": "http://target/backup",
            "status": 301,
            "length": 178,
            "words": 6,
            "lines": 8,
            "content-type": "text/html",
            "redirectlocation": "/backup/",
            "duration": 32,
        },
        {
            "input": {"FUZZ": ".git"},
            "url": "http://target/.git",
            "status": 403,
            "length": 278,
            "words": 20,
            "lines": 12,
            "content-type": "text/html",
            "redirectlocation": "",
            "duration": 20,
        },
    ],
})


def _make_proc_mock(stdout, stderr="", returncode=0):
    proc = AsyncMock()
    proc.communicate = AsyncMock(
        return_value=(stdout.encode(), stderr.encode())
    )
    proc.returncode = returncode
    proc.wait = AsyncMock()
    return proc


class TestSQLMapTool:

    def setup_method(self):
        self.tool = SQLMapTool()

    def test_metadata(self):
        assert self.tool.name == "sqlmap"
        assert self.tool.binary == "sqlmap"

    def test_parse_output_injectable(self):
        result = self.tool.parse_output(SQLMAP_OUTPUT)
        assert result["injectable"] is True
        assert len(result["parameters"]) == 2
        assert result["parameters"][0]["name"] == "username"
        assert result["backend_dbms"] == "MySQL >= 5.6"
        assert len(result["databases"]) == 3
        assert "myapp_db" in result["databases"]

    def test_parse_output_no_injection(self):
        result = self.tool.parse_output(
            "[*] testing done\n[INFO] no injectable params"
        )
        assert result["injectable"] is False
        assert len(result["parameters"]) == 0

    @pytest.mark.asyncio
    @patch("tools.base_tool.scope_guard")
    @patch("asyncio.create_subprocess_exec")
    async def test_execute(self, mock_exec, mock_scope):
        mock_scope.validate_target = MagicMock(return_value=True)
        mock_exec.return_value = _make_proc_mock(SQLMAP_OUTPUT)

        result = await self.tool.execute({
            "target": "http://10.10.10.5/login.php?username=test",
            "level": 2,
        })
        assert result.success
        assert result.parsed_data["injectable"] is True

    @pytest.mark.asyncio
    @patch("tools.base_tool.scope_guard")
    async def test_default_timeout_is_180_seconds(self, mock_scope):
        mock_scope.validate_target = MagicMock(return_value=True)
        self.tool.is_available = AsyncMock(return_value=True)

        async def _fake_run_command(args, *, timeout=300, cwd=None):
            from tools.base_tool import ToolResult

            return ToolResult(tool_name="sqlmap", success=True)

        self.tool.run_command = AsyncMock(side_effect=_fake_run_command)

        await self.tool.execute({
            "target": "http://10.10.10.5/item.php?id=1",
        })

        assert self.tool.run_command.await_args.kwargs["timeout"] == 180


class TestFFUFTool:

    def setup_method(self):
        self.tool = FFUFTool()

    def test_metadata(self):
        assert self.tool.name == "ffuf"
        assert self.tool.binary == "ffuf"

    def test_parse_json_output(self):
        result = self.tool.parse_output(FFUF_JSON_OUTPUT)
        assert result["total"] == 3
        assert result["results"][0]["input"] == "admin"
        assert result["results"][0]["status"] == 200
        assert 200 in result["status_groups"]
        assert "admin" in result["status_groups"][200]

    def test_parse_empty(self):
        result = self.tool.parse_output(json.dumps({"results": []}))
        assert result["total"] == 0

    @pytest.mark.asyncio
    @patch("tools.base_tool.scope_guard")
    @patch("asyncio.create_subprocess_exec")
    async def test_execute(self, mock_exec, mock_scope):
        mock_scope.validate_target = MagicMock(return_value=True)
        mock_exec.return_value = _make_proc_mock(FFUF_JSON_OUTPUT)

        result = await self.tool.execute({
            "target": "http://10.10.10.5/FUZZ",
            "wordlist": "/tmp/wordlist.txt",
        })
        assert result.success
        assert result.parsed_data["total"] == 3
