"""AgentPent — Nmap Tool Unit Tests.

Subprocess mock'lanarak test edilir.
"""

import asyncio
import textwrap
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from tools.nmap_tool import NmapTool

# ── Fixtures ─────────────────────────────────────────────

NMAP_XML_OUTPUT = textwrap.dedent("""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE nmaprun>
<nmaprun scanner="nmap" start="1711545600">
  <scaninfo type="syn" protocol="tcp" services="1-1000"/>
  <host>
    <status state="up"/>
    <address addr="10.10.10.5" addrtype="ipv4"/>
    <hostnames>
      <hostname name="target.lab" type="PTR"/>
    </hostnames>
    <ports>
      <port protocol="tcp" portid="22">
        <state state="open"/>
        <service name="ssh" product="OpenSSH" version="8.9p1"/>
      </port>
      <port protocol="tcp" portid="80">
        <state state="open"/>
        <service name="http" product="Apache httpd" version="2.4.54"/>
      </port>
      <port protocol="tcp" portid="443">
        <state state="open"/>
        <service name="https" product="nginx" version="1.24.0"/>
      </port>
    </ports>
  </host>
</nmaprun>
""")


def _make_proc_mock(stdout: str, stderr: str = "", returncode: int = 0):
    """Subprocess mock oluştur."""
    proc = AsyncMock()
    proc.communicate = AsyncMock(
        return_value=(stdout.encode(), stderr.encode())
    )
    proc.returncode = returncode
    proc.wait = AsyncMock()
    return proc


# ── Tests ────────────────────────────────────────────────


class TestNmapTool:

    def setup_method(self):
        self.tool = NmapTool()

    def test_metadata(self):
        assert self.tool.name == "nmap"
        assert self.tool.binary == "nmap"

    def test_parse_xml_output(self):
        result = self.tool.parse_output(NMAP_XML_OUTPUT)
        assert "hosts" in result
        assert len(result["hosts"]) == 1

        host = result["hosts"][0]
        assert host["addresses"][0]["addr"] == "10.10.10.5"
        assert host["hostnames"] == ["target.lab"]
        assert host["status"] == "up"
        assert len(host["ports"]) == 3

        ssh = host["ports"][0]
        assert ssh["port"] == 22
        assert ssh["state"] == "open"
        assert ssh["service"]["name"] == "ssh"
        assert ssh["service"]["product"] == "OpenSSH"

    def test_parse_invalid_xml(self):
        result = self.tool.parse_output("not xml at all")
        assert "raw" in result

    def test_parse_empty_xml(self):
        result = self.tool.parse_output(
            '<?xml version="1.0"?><nmaprun></nmaprun>'
        )
        assert result["hosts"] == []

    @pytest.mark.asyncio
    @patch("tools.base_tool.scope_guard")
    @patch("asyncio.create_subprocess_exec")
    async def test_execute_quick_scan(self, mock_exec, mock_scope):
        mock_scope.validate_target = MagicMock(return_value=True)
        mock_exec.return_value = _make_proc_mock(NMAP_XML_OUTPUT)

        result = await self.tool.execute({
            "target": "10.10.10.5",
            "scan_type": "quick",
        })

        assert result.success
        assert result.parsed_data["hosts"][0]["addresses"][0]["addr"] == "10.10.10.5"

    @pytest.mark.asyncio
    @patch("tools.base_tool.scope_guard")
    async def test_scope_guard_blocks(self, mock_scope):
        from core.scope_guard import OutOfScopeError
        mock_scope.validate_target = MagicMock(
            side_effect=OutOfScopeError("kapsam dışı")
        )

        result = await self.tool.execute({"target": "8.8.8.8"})
        assert not result.success
        assert "kapsam dışı" in result.error

    @pytest.mark.asyncio
    @patch("tools.base_tool.scope_guard")
    @patch("asyncio.create_subprocess_exec")
    async def test_execute_with_ports(self, mock_exec, mock_scope):
        mock_scope.validate_target = MagicMock(return_value=True)
        mock_exec.return_value = _make_proc_mock(NMAP_XML_OUTPUT)

        result = await self.tool.execute({
            "target": "10.10.10.5",
            "scan_type": "full",
            "ports": "1-65535",
        })

        assert result.success
        # Komutta -p parametresi olmalı
        assert "-p" in result.command

    @pytest.mark.asyncio
    @patch("tools.base_tool.scope_guard")
    async def test_service_scan_requires_explicit_ports(self, mock_scope):
        mock_scope.validate_target = MagicMock(return_value=True)
        self.tool.is_available = AsyncMock(return_value=True)

        result = await self.tool.execute({
            "target": "10.10.10.5",
            "scan_type": "service",
        })

        assert not result.success
        assert "explicit ports" in result.error

    @pytest.mark.asyncio
    @patch("tools.base_tool.scope_guard")
    async def test_protected_scan_rejects_full_range_ports(self, mock_scope):
        mock_scope.validate_target = MagicMock(return_value=True)
        self.tool.is_available = AsyncMock(return_value=True)

        result = await self.tool.execute({
            "target": "10.10.10.5",
            "scan_type": "quick",
            "ports": "1-65535",
        })

        assert not result.success
        assert "tam port aralığı" in result.error

    @pytest.mark.asyncio
    @patch("tools.base_tool.scope_guard")
    @patch("asyncio.create_subprocess_exec")
    async def test_protected_scan_sanitizes_unsafe_extra_flags(self, mock_exec, mock_scope):
        mock_scope.validate_target = MagicMock(return_value=True)
        mock_exec.return_value = _make_proc_mock(NMAP_XML_OUTPUT)

        result = await self.tool.execute({
            "target": "10.10.10.5",
            "scan_type": "quick",
            "extra_flags": ["-O", "--script=vuln", "--script-trace"],
        })

        assert result.success
        assert "-O" not in result.command
        assert "--script=vuln" not in result.command
        assert "--script-trace" not in result.command
