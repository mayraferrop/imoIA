"""Testes para AI scoring enrichment — M8 leads."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.modules.m8_leads.service import (
    _compute_ai_hash,
    _enrich_score_with_ai,
    _ai_cache_valid,
    _calculate_grade,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_lead(**overrides):
    """Cria um lead dict de teste."""
    base = {
        "id": "lead-test-1",
        "name": "Carlos Mendes",
        "email": "carlos@test.com",
        "phone": "+351912345678",
        "budget_min": 150000,
        "budget_max": 300000,
        "preferred_typology": "T2",
        "preferred_locations": ["Lisboa", "Porto"],
        "timeline": "imediato",
        "financing": "pre_approved",
        "buyer_type": "investor",
        "stage": "qualified",
        "source": "habta.eu",
        "notes": "Investidor brasileiro, procura T2 em Lisboa para fix & flip.",
        "tags": ["investor", "brasil"],
        "score": 55,
        "score_breakdown": {},
    }
    base.update(overrides)
    return base


def _mock_ai_response(adjustment=10, confidence="high", reasoning="Bom lead", signals=None):
    """Cria mock da resposta do Claude."""
    return json.dumps({
        "adjustment": adjustment,
        "confidence": confidence,
        "reasoning": reasoning,
        "signals": signals or ["investor profile", "budget realista"],
    })


# ---------------------------------------------------------------------------
# test_ai_adjustment_in_range
# ---------------------------------------------------------------------------

class TestAIAdjustmentInRange:
    @patch("src.modules.m8_leads.service.db")
    @patch("src.config.get_settings")
    def test_adjustment_clamped_positive(self, mock_settings, mock_db):
        mock_settings.return_value = MagicMock(anthropic_api_key="sk-test")
        mock_db._count.return_value = 3

        with patch("anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = MagicMock(
                content=[MagicMock(text=_mock_ai_response(adjustment=50))]
            )

            lead = _make_lead(score=80)
            result = _enrich_score_with_ai(lead, 80, force=True)

            # Adjustment clamped to +30, final capped at 100
            assert result["adjustment"] <= 30
            assert result["final_score"] <= 100

    @patch("src.modules.m8_leads.service.db")
    @patch("src.config.get_settings")
    def test_adjustment_clamped_negative(self, mock_settings, mock_db):
        mock_settings.return_value = MagicMock(anthropic_api_key="sk-test")
        mock_db._count.return_value = 0

        with patch("anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = MagicMock(
                content=[MagicMock(text=_mock_ai_response(adjustment=-50))]
            )

            lead = _make_lead(score=10)
            result = _enrich_score_with_ai(lead, 10, force=True)

            assert result["adjustment"] >= -30
            assert result["final_score"] >= 0


# ---------------------------------------------------------------------------
# test_graceful_degradation_no_api_key
# ---------------------------------------------------------------------------

class TestGracefulDegradationNoApiKey:
    @patch("src.modules.m8_leads.service.db")
    @patch("src.config.get_settings")
    def test_returns_neutral_without_key(self, mock_settings, mock_db):
        mock_settings.return_value = MagicMock(anthropic_api_key="")
        mock_db._count.return_value = 0

        lead = _make_lead()
        result = _enrich_score_with_ai(lead, 55)

        assert result["adjustment"] == 0
        assert result["confidence"] == "none"
        assert result["final_score"] == 55
        assert "nao configurada" in result["reasoning"]


# ---------------------------------------------------------------------------
# test_graceful_degradation_api_error
# ---------------------------------------------------------------------------

class TestGracefulDegradationApiError:
    @patch("src.modules.m8_leads.service.db")
    @patch("src.config.get_settings")
    def test_returns_neutral_on_api_error(self, mock_settings, mock_db):
        mock_settings.return_value = MagicMock(anthropic_api_key="sk-test")
        mock_db._count.return_value = 2

        with patch("anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = Exception("API timeout")

            lead = _make_lead()
            result = _enrich_score_with_ai(lead, 55, force=True)

            assert result["adjustment"] == 0
            assert result["final_score"] == 55
            assert "Erro" in result["reasoning"]

    @patch("src.modules.m8_leads.service.db")
    @patch("src.config.get_settings")
    def test_returns_neutral_on_json_error(self, mock_settings, mock_db):
        mock_settings.return_value = MagicMock(anthropic_api_key="sk-test")
        mock_db._count.return_value = 1

        with patch("anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = MagicMock(
                content=[MagicMock(text="not valid json at all")]
            )

            lead = _make_lead()
            result = _enrich_score_with_ai(lead, 55, force=True)

            assert result["adjustment"] == 0
            assert "Erro" in result["reasoning"]


# ---------------------------------------------------------------------------
# test_cache_skip_if_unchanged
# ---------------------------------------------------------------------------

class TestCacheSkipIfUnchanged:
    @patch("src.modules.m8_leads.service.db")
    @patch("src.config.get_settings")
    def test_cache_hit_returns_existing(self, mock_settings, mock_db):
        mock_settings.return_value = MagicMock(anthropic_api_key="sk-test")
        mock_db._count.return_value = 3

        lead = _make_lead()
        cache_hash = _compute_ai_hash(lead, 3)

        lead["score_breakdown"] = {
            "ai_enrichment": {
                "adjustment": 10,
                "confidence": "high",
                "reasoning": "Cached result",
                "signals": ["cached"],
                "final_score": 65,
                "last_run_at": datetime.utcnow().isoformat(),
                "cache_hash": cache_hash,
            }
        }

        # Nao deve chamar anthropic
        result = _enrich_score_with_ai(lead, 55, force=False)
        assert result["reasoning"] == "Cached result"
        assert result["adjustment"] == 10


# ---------------------------------------------------------------------------
# test_cache_invalidate_after_days
# ---------------------------------------------------------------------------

class TestCacheInvalidateAfterDays:
    @patch("src.modules.m8_leads.service.db")
    @patch("src.config.get_settings")
    def test_stale_cache_calls_api(self, mock_settings, mock_db):
        mock_settings.return_value = MagicMock(anthropic_api_key="sk-test")
        mock_db._count.return_value = 3

        lead = _make_lead()
        cache_hash = _compute_ai_hash(lead, 3)

        # Cache com 10 dias (> 7 dias = invalido)
        old_date = (datetime.utcnow() - timedelta(days=10)).isoformat()
        lead["score_breakdown"] = {
            "ai_enrichment": {
                "adjustment": 5,
                "confidence": "medium",
                "reasoning": "Old cached",
                "signals": [],
                "final_score": 60,
                "last_run_at": old_date,
                "cache_hash": cache_hash,
            }
        }

        with patch("anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = MagicMock(
                content=[MagicMock(text=_mock_ai_response(adjustment=15, reasoning="Fresh analysis"))]
            )

            result = _enrich_score_with_ai(lead, 55, force=False)
            assert result["reasoning"] == "Fresh analysis"
            assert result["adjustment"] == 15
            mock_client.messages.create.assert_called_once()


# ---------------------------------------------------------------------------
# test_ai_cache_valid
# ---------------------------------------------------------------------------

class TestAICacheValid:
    @patch("src.modules.m8_leads.service.db")
    def test_valid_cache(self, mock_db):
        mock_db._count.return_value = 3
        lead = _make_lead()
        cache_hash = _compute_ai_hash(lead, 3)

        lead["score_breakdown"] = {
            "ai_enrichment": {
                "last_run_at": datetime.utcnow().isoformat(),
                "cache_hash": cache_hash,
            }
        }
        assert _ai_cache_valid(lead) is True

    @patch("src.modules.m8_leads.service.db")
    def test_invalid_cache_no_enrichment(self, mock_db):
        lead = _make_lead()
        lead["score_breakdown"] = {}
        assert _ai_cache_valid(lead) is False

    @patch("src.modules.m8_leads.service.db")
    def test_invalid_cache_old(self, mock_db):
        mock_db._count.return_value = 3
        lead = _make_lead()
        cache_hash = _compute_ai_hash(lead, 3)

        old_date = (datetime.utcnow() - timedelta(days=10)).isoformat()
        lead["score_breakdown"] = {
            "ai_enrichment": {
                "last_run_at": old_date,
                "cache_hash": cache_hash,
            }
        }
        assert _ai_cache_valid(lead) is False

    @patch("src.modules.m8_leads.service.db")
    def test_invalid_cache_hash_mismatch(self, mock_db):
        mock_db._count.return_value = 3
        lead = _make_lead()

        lead["score_breakdown"] = {
            "ai_enrichment": {
                "last_run_at": datetime.utcnow().isoformat(),
                "cache_hash": "old-wrong-hash",
            }
        }
        assert _ai_cache_valid(lead) is False


# ---------------------------------------------------------------------------
# test_grade_recalculates_after_adjustment
# ---------------------------------------------------------------------------

class TestGradeRecalculatesAfterAdjustment:
    def test_upgrade_grade(self):
        # Score 65 = B, +10 adjustment = 75 = A
        assert _calculate_grade(65) == "B"
        assert _calculate_grade(75) == "A"

    def test_downgrade_grade(self):
        # Score 32 = C, -5 adjustment = 27 = D
        assert _calculate_grade(32) == "C"
        assert _calculate_grade(27) == "D"


# ---------------------------------------------------------------------------
# Integration: enrich + final score + grade
# ---------------------------------------------------------------------------

class TestAIScoringIntegration:
    @patch("src.modules.m8_leads.service.db")
    @patch("src.config.get_settings")
    def test_full_enrichment_flow(self, mock_settings, mock_db):
        """Testa fluxo completo: AI chamada, adjustment aplicado, campos populados."""
        mock_settings.return_value = MagicMock(anthropic_api_key="sk-test")
        mock_db._count.return_value = 5

        with patch("anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = MagicMock(
                content=[MagicMock(text=_mock_ai_response(
                    adjustment=15,
                    confidence="high",
                    reasoning="Investidor qualificado com budget realista",
                    signals=["investor", "budget ok", "timeline urgente"],
                ))]
            )

            lead = _make_lead()
            result = _enrich_score_with_ai(lead, 55, force=True)

            assert result["adjustment"] == 15
            assert result["confidence"] == "high"
            assert result["final_score"] == 70
            assert "Investidor" in result["reasoning"]
            assert len(result["signals"]) == 3
            assert result["cache_hash"]
            assert result["last_run_at"]

            # Segunda call sem force: deve usar cache
            lead["score_breakdown"] = {"ai_enrichment": result}
            mock_client.messages.create.reset_mock()

            cached = _enrich_score_with_ai(lead, 55, force=False)
            assert cached["adjustment"] == 15
            mock_client.messages.create.assert_not_called()
