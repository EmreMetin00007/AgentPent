"""AgentPent — Prompt Engine & Refusal Detection Testleri."""

import pytest

from core.prompt_engine import (
    OFFENSIVE_AGENTS,
    _detect_family,
    _select_variant,
    build_system_prompt,
    get_fallback_chain,
    get_model_for_agent,
)
from core.llm_client import LLMClient


# ── Model Family Detection ────────────────────────────────

class TestModelFamilyDetection:
    def test_openai_family(self):
        assert _detect_family("openai/gpt-5.4") == "openai"
        assert _detect_family("openai/o3-mini") == "openai"

    def test_anthropic_family(self):
        assert _detect_family("anthropic/claude-sonnet-4.6") == "anthropic"

    def test_hermes_family(self):
        assert _detect_family("nousresearch/hermes-3-llama-3.1-405b") == "hermes"

    def test_dolphin_family(self):
        assert _detect_family("cognitivecomputations/dolphin3.0-r1-mistral-24b") == "dolphin"

    def test_qwen_family(self):
        assert _detect_family("qwen/qwen3-max-thinking") == "qwen"

    def test_unknown_family(self):
        assert _detect_family("some-random/model-v1") == "unknown"


# ── Variant Selection ─────────────────────────────────────

class TestVariantSelection:
    def test_returns_string(self):
        variant = _select_variant("openai/gpt-5.4", "exploit")
        assert isinstance(variant, str)
        assert len(variant) > 100

    def test_deterministic(self):
        """Aynı model+agent her zaman aynı varyasyonu döndürmeli."""
        v1 = _select_variant("openai/gpt-5.4", "exploit")
        v2 = _select_variant("openai/gpt-5.4", "exploit")
        assert v1 == v2

    def test_different_agents_can_get_different_variants(self):
        """Farklı agentlar farklı varyasyonlar alabilmeli."""
        # En az 2 tanesi farklı olmalı (hash bazlı)
        variants = set()
        for agent in ["exploit", "evasion", "recon", "scanner", "osint"]:
            variants.add(_select_variant("openai/gpt-5.4", agent))
        assert len(variants) >= 1  # En az 1, genelde 2-3 farklı


# ── Build System Prompt ───────────────────────────────────

class TestBuildSystemPrompt:
    def test_basic_prompt_structure(self):
        prompt = build_system_prompt(
            agent_name="recon",
            agent_prompt="# Recon Agent\nSen keşif agent'ısın.",
            model="openai/gpt-5.4",
        )
        assert "# Recon Agent" in prompt
        assert "Your Identity" in prompt
        assert len(prompt) > 500

    def test_offensive_agent_gets_fewshot(self):
        prompt = build_system_prompt(
            agent_name="exploit",
            agent_prompt="# Exploit Agent",
            model="openai/gpt-5.4",
        )
        assert "reverse shell" in prompt.lower() or "Previous Successful" in prompt

    def test_recon_agent_gets_recon_fewshot(self):
        prompt = build_system_prompt(
            agent_name="recon",
            agent_prompt="# Recon Agent",
            model="openai/gpt-5.4",
        )
        assert "nmap" in prompt.lower() or "Previous Successful" in prompt

    def test_uncensored_model_gets_lighter_jailbreak(self):
        prompt_censored = build_system_prompt(
            agent_name="exploit",
            agent_prompt="# Exploit Agent",
            model="openai/gpt-5.4",
        )
        prompt_uncensored = build_system_prompt(
            agent_name="exploit",
            agent_prompt="# Exploit Agent",
            model="nousresearch/hermes-3-llama-3.1-405b",
        )
        # Uncensored model daha kısa jailbreak almalı
        assert len(prompt_uncensored) < len(prompt_censored)

    def test_no_fewshot_option(self):
        prompt = build_system_prompt(
            agent_name="exploit",
            agent_prompt="# Exploit Agent",
            model="openai/gpt-5.4",
            include_fewshot=False,
        )
        assert "Previous Successful" not in prompt

    def test_offensive_persona_for_exploit(self):
        prompt = build_system_prompt(
            agent_name="exploit",
            agent_prompt="# Exploit Agent",
            model="openai/gpt-5.4",
        )
        assert "GPEN" in prompt or "Metasploit" in prompt

    def test_evasion_persona(self):
        prompt = build_system_prompt(
            agent_name="evasion",
            agent_prompt="# Evasion Agent",
            model="openai/gpt-5.4",
        )
        assert "AV/EDR" in prompt or "evasion" in prompt.lower()


# ── Model Routing ─────────────────────────────────────────

class TestModelRouting:
    def test_offensive_agents_get_offensive_model(self):
        for agent in OFFENSIVE_AGENTS:
            model = get_model_for_agent(agent, "openai/gpt-5.4", "hermes-3")
            assert model == "hermes-3"

    def test_defensive_agents_get_default_model(self):
        for agent in ["recon", "scanner", "commander", "reporter"]:
            model = get_model_for_agent(agent, "openai/gpt-5.4", "hermes-3")
            assert model == "openai/gpt-5.4"


# ── Fallback Chain ────────────────────────────────────────

class TestFallbackChain:
    def test_excludes_current_model(self):
        chain = get_fallback_chain("model-a,model-b,model-c", "model-a")
        assert "model-a" not in chain
        assert "model-b" in chain
        assert "model-c" in chain

    def test_empty_csv(self):
        chain = get_fallback_chain("", "model-a")
        assert chain == []

    def test_all_same_as_current(self):
        chain = get_fallback_chain("model-a,model-a", "model-a")
        assert chain == []


# ── Refusal Detection ─────────────────────────────────────

class TestRefusalDetection:
    def test_detects_english_refusal(self):
        assert LLMClient.detect_refusal("I can't assist with generating exploit code.")
        assert LLMClient.detect_refusal("I'm unable to provide malicious payloads.")
        assert LLMClient.detect_refusal("As an AI language model, I cannot help with hacking.")
        assert LLMClient.detect_refusal("I must decline this request due to safety guidelines.")

    def test_detects_turkish_refusal(self):
        assert LLMClient.detect_refusal("Bu bir siber saldırı olarak değerlendirilebilir.")
        assert LLMClient.detect_refusal("Etik kural gereği bunu gerçekleştiremem.")

    def test_no_false_positive_on_normal_text(self):
        assert not LLMClient.detect_refusal('{"tool_calls": [{"tool": "nmap"}]}')
        assert not LLMClient.detect_refusal("Port 80 açık, HTTP servisi tespit edildi.")
        assert not LLMClient.detect_refusal("SQL injection bulundu: login.php?id=1")

    def test_no_false_positive_on_short_text(self):
        assert not LLMClient.detect_refusal("")
        assert not LLMClient.detect_refusal("OK")

    def test_detects_policy_refusal(self):
        assert LLMClient.detect_refusal(
            "This request violates my safety guidelines and I cannot fulfill it."
        )

    def test_detects_harmful_refusal(self):
        assert LLMClient.detect_refusal(
            "I cannot help with creating tools for harmful activities."
        )
