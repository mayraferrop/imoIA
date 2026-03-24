"""Testes M5 — Due Diligence.

Testa templates, geracao de checklist, red flags, can_proceed, e documentos.
"""

from __future__ import annotations

import pytest

from src.modules.m5_due_diligence.templates import (
    PT_BASE_CHECKLIST,
    BR_BASE_CHECKLIST,
    PT_EXTRA_BY_TYPE,
    PT_EXTRA_BY_STRATEGY,
    get_checklist_template,
)


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


class TestTemplates:
    """Testa templates de checklist."""

    def test_pt_base_has_items(self) -> None:
        assert len(PT_BASE_CHECKLIST) >= 13

    def test_br_base_has_items(self) -> None:
        assert len(BR_BASE_CHECKLIST) >= 7

    def test_pt_base_has_certidao_predial(self) -> None:
        keys = [i["item_key"] for i in PT_BASE_CHECKLIST]
        assert "certidao_predial" in keys
        assert "caderneta_predial" in keys
        assert "certificado_energetico" in keys

    def test_br_has_matricula(self) -> None:
        keys = [i["item_key"] for i in BR_BASE_CHECKLIST]
        assert "matricula_atualizada" in keys

    def test_pt_predio_extras(self) -> None:
        extras = PT_EXTRA_BY_TYPE.get("predio", [])
        keys = [i["item_key"] for i in extras]
        assert "propriedade_horizontal" in keys

    def test_pt_terreno_extras(self) -> None:
        extras = PT_EXTRA_BY_TYPE.get("terreno", [])
        keys = [i["item_key"] for i in extras]
        assert "viabilidade_construcao" in keys
        assert "ren_ran" in keys

    def test_pt_al_strategy(self) -> None:
        extras = PT_EXTRA_BY_STRATEGY.get("alojamento_local", [])
        keys = [i["item_key"] for i in extras]
        assert "licenca_al" in keys

    def test_pt_wholesale_strategy(self) -> None:
        extras = PT_EXTRA_BY_STRATEGY.get("wholesale", [])
        keys = [i["item_key"] for i in extras]
        assert "clausula_cessao" in keys

    def test_get_template_pt_apartamento(self) -> None:
        items = get_checklist_template("PT", "apartamento", "fix_and_flip")
        assert len(items) >= 13  # base + strategy extra
        keys = [i["item_key"] for i in items]
        assert "certidao_predial" in keys
        assert "comunicacao_previa" in keys  # fix_and_flip extra

    def test_get_template_pt_predio(self) -> None:
        items = get_checklist_template("PT", "predio", "fix_and_flip")
        keys = [i["item_key"] for i in items]
        assert "propriedade_horizontal" in keys

    def test_get_template_pt_terreno(self) -> None:
        items = get_checklist_template("PT", "terreno", "desenvolvimento")
        keys = [i["item_key"] for i in items]
        assert "viabilidade_construcao" in keys
        assert "topografia" in keys
        assert "ren_ran" in keys
        assert "projecto_arquitectura" in keys

    def test_get_template_br(self) -> None:
        items = get_checklist_template("BR", "apartamento", "fix_and_flip")
        keys = [i["item_key"] for i in items]
        assert "matricula_atualizada" in keys
        assert "certidao_predial" not in keys  # PT only

    def test_items_sorted(self) -> None:
        items = get_checklist_template("PT", "apartamento", "fix_and_flip")
        orders = [i["sort_order"] for i in items]
        assert orders == sorted(orders)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class TestDueDiligenceService:
    """Testa o service com BD SQLite em memoria."""

    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path):
        import os
        os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/test.db"
        from src.database.db import reset_engine, _get_engine
        from src.database.models import Base
        reset_engine()
        import src.database.models_v2  # noqa: F401
        engine = _get_engine()
        Base.metadata.create_all(bind=engine)
        self.service = __import__(
            "src.modules.m5_due_diligence.service",
            fromlist=["DueDiligenceService"],
        ).DueDiligenceService()
        self.m4_service = __import__(
            "src.modules.m4_deal_pipeline.service",
            fromlist=["DealPipelineService"],
        ).DealPipelineService()
        self.tmp_path = tmp_path
        yield
        from src.database.db import reset_engine as re
        re()

    def _create_deal(
        self, property_type: str = "apartamento", country: str = "PT",
        strategy: str = "fix_and_flip",
    ) -> dict:
        from uuid import uuid4
        from src.database.db import get_session
        from src.database.models_v2 import Property, Tenant
        from sqlalchemy import select
        with get_session() as session:
            tenant = session.execute(
                select(Tenant).where(Tenant.slug == "default")
            ).scalar_one_or_none()
            if not tenant:
                tenant = Tenant(
                    id=str(uuid4()), name="Test", slug="default", country="PT"
                )
                session.add(tenant)
                session.flush()
            prop = Property(
                id=str(uuid4()), tenant_id=tenant.id, source="test",
                country=country, municipality="Lisboa",
                property_type=property_type, asking_price=200000,
                status="lead",
            )
            session.add(prop)
            session.flush()
            prop_id = prop.id

        return self.m4_service.create_deal({
            "property_id": prop_id,
            "investment_strategy": strategy,
            "title": f"Test DD ({property_type}, {country})",
            "purchase_price": 200000,
        })

    def test_generate_pt_checklist(self) -> None:
        deal = self._create_deal("apartamento", "PT", "fix_and_flip")
        result = self.service.generate_checklist(deal["id"])
        assert result["total_items"] >= 13
        assert result["country"] == "PT"

    def test_generate_br_checklist(self) -> None:
        deal = self._create_deal("apartamento", "BR", "fix_and_flip")
        result = self.service.generate_checklist(deal["id"])
        assert result["country"] == "BR"
        keys = [i["item_key"] for i in result["items"]]
        assert "matricula_atualizada" in keys

    def test_predio_has_extra_items(self) -> None:
        deal = self._create_deal("predio", "PT")
        result = self.service.generate_checklist(deal["id"])
        keys = [i["item_key"] for i in result["items"]]
        assert "propriedade_horizontal" in keys

    def test_terreno_has_viabilidade(self) -> None:
        deal = self._create_deal("terreno", "PT", "desenvolvimento")
        result = self.service.generate_checklist(deal["id"])
        keys = [i["item_key"] for i in result["items"]]
        assert "viabilidade_construcao" in keys
        assert "topografia" in keys
        assert "ren_ran" in keys

    def test_al_has_licenca_al(self) -> None:
        deal = self._create_deal("apartamento", "PT", "alojamento_local")
        result = self.service.generate_checklist(deal["id"])
        keys = [i["item_key"] for i in result["items"]]
        assert "licenca_al" in keys

    def test_wholesale_has_cessao(self) -> None:
        deal = self._create_deal("apartamento", "PT", "wholesale")
        result = self.service.generate_checklist(deal["id"])
        keys = [i["item_key"] for i in result["items"]]
        assert "clausula_cessao" in keys

    def test_condominio_not_required_for_moradia(self) -> None:
        deal = self._create_deal("moradia", "PT")
        result = self.service.generate_checklist(deal["id"])
        condo_items = [
            i for i in result["items"]
            if i.get("category") == "condominio"
        ]
        for item in condo_items:
            assert item["is_required"] is False

    def test_get_checklist(self) -> None:
        deal = self._create_deal()
        self.service.generate_checklist(deal["id"])
        checklist = self.service.get_checklist(deal["id"])
        assert checklist["total_items"] >= 13
        assert checklist["progress_pct"] == 0.0
        assert "items_by_category" in checklist

    def test_update_item_status(self) -> None:
        deal = self._create_deal()
        result = self.service.generate_checklist(deal["id"])
        item_id = result["items"][0]["id"]
        updated = self.service.update_item(item_id, {"status": "obtido"})
        assert updated["status"] == "obtido"
        assert updated["verified_at"] is not None

    def test_add_red_flag(self) -> None:
        deal = self._create_deal()
        result = self.service.generate_checklist(deal["id"])
        item_id = result["items"][0]["id"]
        flagged = self.service.add_red_flag(
            item_id, "high", "Penhora activa registada"
        )
        assert flagged["red_flag"] is True
        assert flagged["red_flag_severity"] == "high"

    def test_resolve_red_flag(self) -> None:
        deal = self._create_deal()
        result = self.service.generate_checklist(deal["id"])
        item_id = result["items"][0]["id"]
        self.service.add_red_flag(item_id, "high", "Penhora")
        resolved = self.service.resolve_red_flag(item_id, "Penhora cancelada")
        assert resolved["red_flag"] is False
        assert "Penhora cancelada" in (resolved.get("verification_notes") or "")

    def test_can_proceed_all_done(self) -> None:
        deal = self._create_deal()
        result = self.service.generate_checklist(deal["id"])
        for item in result["items"]:
            self.service.update_item(item["id"], {"status": "obtido"})
        check = self.service.can_proceed(deal["id"])
        assert check["can_proceed"] is True

    def test_cannot_proceed_pending(self) -> None:
        deal = self._create_deal()
        self.service.generate_checklist(deal["id"])
        check = self.service.can_proceed(deal["id"])
        assert check["can_proceed"] is False
        assert len(check["blocking_items"]) > 0

    def test_cannot_proceed_critical_flag(self) -> None:
        deal = self._create_deal()
        result = self.service.generate_checklist(deal["id"])
        # Mark all as done
        for item in result["items"]:
            self.service.update_item(item["id"], {"status": "obtido"})
        # Add critical flag
        self.service.add_red_flag(
            result["items"][0]["id"], "critical", "Fraude"
        )
        check = self.service.can_proceed(deal["id"])
        assert check["can_proceed"] is False
        assert len(check["critical_flags"]) == 1

    def test_can_proceed_with_medium_flag(self) -> None:
        deal = self._create_deal()
        result = self.service.generate_checklist(deal["id"])
        for item in result["items"]:
            self.service.update_item(item["id"], {"status": "obtido"})
        self.service.add_red_flag(
            result["items"][0]["id"], "medium", "VPT desactualizado"
        )
        check = self.service.can_proceed(deal["id"])
        assert check["can_proceed"] is True
        assert len(check["warnings"]) == 1

    def test_add_custom_item(self) -> None:
        deal = self._create_deal()
        self.service.generate_checklist(deal["id"])
        custom = self.service.add_custom_item(deal["id"], {
            "category": "outro",
            "item_name": "Verificacao especial",
            "description": "Item personalizado",
            "is_required": False,
        })
        assert custom["item_name"] == "Verificacao especial"
        assert custom["item_key"].startswith("custom_")

    def test_auto_generate_on_advance(self) -> None:
        """Checklist gerado automaticamente quando deal entra em due_diligence."""
        deal = self._create_deal()
        # Advance to due_diligence
        for target in ["oportunidade", "analise", "proposta",
                        "negociacao", "cpcv_compra", "due_diligence"]:
            deal = self.m4_service.advance_deal(deal["id"], target)

        checklist = self.service.get_checklist(deal["id"])
        assert checklist["total_items"] >= 13

    def test_progress_calculation(self) -> None:
        deal = self._create_deal()
        result = self.service.generate_checklist(deal["id"])
        total = len(result["items"])
        # Mark half as done
        half = total // 2
        for item in result["items"][:half]:
            self.service.update_item(item["id"], {"status": "obtido"})
        checklist = self.service.get_checklist(deal["id"])
        assert checklist["progress_pct"] > 0

    def test_get_red_flags(self) -> None:
        deal = self._create_deal()
        result = self.service.generate_checklist(deal["id"])
        self.service.add_red_flag(
            result["items"][0]["id"], "high", "Problema 1"
        )
        self.service.add_red_flag(
            result["items"][1]["id"], "critical", "Problema 2"
        )
        flags = self.service.get_red_flags(deal["id"])
        assert len(flags) == 2

    def test_dd_stats(self) -> None:
        deal = self._create_deal()
        self.service.generate_checklist(deal["id"])
        stats = self.service.get_dd_stats()
        assert stats["total_checklists"] >= 1

    # --- Document tests ---

    def test_upload_document_to_item(self) -> None:
        import os
        os.environ["STORAGE_BASE"] = str(self.tmp_path / "storage")
        deal = self._create_deal()
        result = self.service.generate_checklist(deal["id"])
        item_id = result["items"][0]["id"]
        doc = self.service.upload_item_document(
            item_id, b"%PDF-1.4 fake content", "certidao.pdf",
            storage_base=str(self.tmp_path / "storage"),
        )
        assert doc["filename"] == "certidao.pdf"
        assert doc["dd_item_id"] == item_id

    def test_list_item_documents(self) -> None:
        deal = self._create_deal()
        result = self.service.generate_checklist(deal["id"])
        item_id = result["items"][0]["id"]
        self.service.upload_item_document(
            item_id, b"content1", "doc1.pdf",
            storage_base=str(self.tmp_path / "storage"),
        )
        self.service.upload_item_document(
            item_id, b"content2", "doc2.pdf",
            storage_base=str(self.tmp_path / "storage"),
        )
        docs = self.service.get_item_documents(item_id)
        assert len(docs) == 2

    def test_remove_item_document(self) -> None:
        deal = self._create_deal()
        result = self.service.generate_checklist(deal["id"])
        item_id = result["items"][0]["id"]
        self.service.upload_item_document(
            item_id, b"content", "doc.pdf",
            storage_base=str(self.tmp_path / "storage"),
        )
        ok = self.service.remove_item_document(
            item_id, storage_base=str(self.tmp_path / "storage"),
        )
        assert ok is True
        docs = self.service.get_item_documents(item_id)
        assert len(docs) == 0
