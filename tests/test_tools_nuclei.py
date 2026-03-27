"""AgentPent — Nuclei Tool Unit Tests."""

import asyncio
import json
import textwrap
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from tools.nuclei_tool import NucleiTool, _extract_cves

# ── Fixtures ─────────────────────────────────────────────

NUCLEI_JSONL_OUTPUT = "\n".join([
    json.dumps({
        "template-id": "apache-path-traversal",
        "info": {
            "name": "Apache HTTP Server Path Traversal",
            "severity": "critical",
            "description": "Apache 2.4.49 path traversal CVE-2021-41773",
            "reference": ["https://nvd.nist.gov/vuln/detail/CVE-2021-41773"],
            "tags": ["cve", "apache", "CVE-2021-41773"],
            "classification": {"cve-id": "CVE-2021-41773"},
        },
        "host": "http://10.10.10.5",
        "matched-at": "http://10.10.10.5/cgi-bin/.%2e/%2e%2e/etc/passwd",
        "matcher-name": "body",
    }),
    json.dumps({
        "template-id": "tech-detect",
        "info": {
            "name": "Apache Detection",
            "severity": "info",
            "description": "Apache web server detected",
            "tags": ["tech", "apache"],
        },
        "host": "http://10.10.10.5",
        "matched-at": "http://10.10.10.5",
    }),
])


def _make_proc_mock(stdout: str, stderr: str = "", returncode: int = 0):
    proc = AsyncMock()
    proc.communicate = AsyncMock(
        return_value=(stdout.encode(), stderr.encode())
    )
    proc.returncode = returncode
    proc.wait = AsyncMock()
    return proc


# ── Tests ────────────────────────────────────────────────


class TestNucleiTool:

    def setup_method(self):
        self.tool = NucleiTool()

    def test_metadata(self):
        assert self.tool.name == "nuclei"
        assert self.tool.binary == "nuclei"

    def test_parse_jsonl_output(self):
        result = self.tool.parse_output(NUCLEI_JSONL_OUTPUT)
        assert result["total"] == 2
        assert result["stats"]["critical"] == 1
        assert result["stats"]["info"] == 1

        findings = result["findings"]
        critical = findings[0]
        assert critical["severity"] == "CRITICAL"
        assert critical["template_id"] == "apache-path-traversal"
        assert "CVE-2021-41773" in critical["cve_ids"]

    def test_parse_empty_output(self):
        result = self.tool.parse_output("")
        assert result["total"] == 0
        assert result["findings"] == []

    def test_parse_invalid_json_lines(self):
        result = self.tool.parse_output("not json\nalso not json\n")
        assert result["total"] == 0

    def test_extract_cves(self):
        item = {
            "info": {
                "classification": {"cve-id": "CVE-2021-41773"},
                "tags": ["cve", "CVE-2021-41773", "apache"],
            }
        }
        cves = _extract_cves(item)
        assert "CVE-2021-41773" in cves

    def test_extract_cves_list(self):
        item = {
            "info": {
                "classification": {
                    "cve-id": ["CVE-2021-41773", "CVE-2021-42013"]
                },
                "tags": [],
            }
        }
        cves = _extract_cves(item)
        assert "CVE-2021-41773" in cves
        assert "CVE-2021-42013" in cves

    @pytest.mark.asyncio
    @patch("tools.base_tool.scope_guard")
    @patch("asyncio.create_subprocess_exec")
    async def test_execute(self, mock_exec, mock_scope):
        mock_scope.validate_target = MagicMock(return_value=True)
        mock_exec.return_value = _make_proc_mock(NUCLEI_JSONL_OUTPUT)

        result = await self.tool.execute({"target": "http://10.10.10.5"})

        assert result.success
        assert result.parsed_data["total"] == 2

    @pytest.mark.asyncio
    @patch("tools.base_tool.scope_guard")
    @patch("asyncio.create_subprocess_exec")
    async def test_execute_with_severity_filter(self, mock_exec, mock_scope):
        mock_scope.validate_target = MagicMock(return_value=True)
        mock_exec.return_value = _make_proc_mock(NUCLEI_JSONL_OUTPUT)

        result = await self.tool.execute({
            "target": "http://10.10.10.5",
            "severity": "critical,high",
        })

        assert result.success
        assert "-severity" in result.command
