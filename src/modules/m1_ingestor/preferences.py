"""Preferencias do utilizador para filtragem e scoring de oportunidades.

Guarda as preferencias em data/preferences.json.
Usado pelo deal_scorer para ajustar pontuacoes e pelo dashboard para destacar matches.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

_PREFS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "preferences.json"

# Preferencias por defeito
_DEFAULTS: Dict[str, Any] = {
    "description": "",
    "property_types": [],
    "opportunity_types": [],
    "locations_include": [],
    "locations_exclude": [],
    "price_min": None,
    "price_max": None,
    "area_min": None,
    "area_max": None,
    "bedrooms_min": None,
    "bedrooms_max": None,
    "max_price_vs_market_pct": None,
    "min_yield_pct": None,
}


def load_preferences() -> Dict[str, Any]:
    """Carrega preferencias do ficheiro JSON."""
    if not _PREFS_FILE.exists():
        return dict(_DEFAULTS)
    try:
        data = json.loads(_PREFS_FILE.read_text(encoding="utf-8"))
        merged = dict(_DEFAULTS)
        merged.update(data)
        return merged
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Erro ao carregar preferencias: {e}")
        return dict(_DEFAULTS)


def save_preferences(prefs: Dict[str, Any]) -> None:
    """Guarda preferencias no ficheiro JSON."""
    _PREFS_FILE.parent.mkdir(exist_ok=True)
    _PREFS_FILE.write_text(
        json.dumps(prefs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Preferencias guardadas")


def match_opportunity(opp: Any, market_data: Any = None) -> Dict[str, Any]:
    """Avalia quanto uma oportunidade encaixa nas preferencias.

    Args:
        opp: Objecto Opportunity (SQLAlchemy) ou dict com campos equivalentes.
        market_data: Objecto MarketData associado (pode ser None).

    Returns:
        Dict com:
            - match_pct: 0-100 (percentagem de match)
            - match_label: str descritivo
            - bonuses: list de str (criterios que encaixam)
            - penalties: list de str (criterios que nao encaixam)
    """
    prefs = load_preferences()
    bonuses: List[str] = []
    penalties: List[str] = []
    total_criteria = 0
    matched_criteria = 0

    # Helper para aceder atributos de ORM ou dict
    def _get(obj: Any, key: str, default: Any = None) -> Any:
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    # --- Tipo de imovel ---
    pref_prop_types = prefs.get("property_types") or []
    if pref_prop_types:
        total_criteria += 1
        prop_type = _get(opp, "property_type")
        if prop_type and prop_type.lower() in [t.lower() for t in pref_prop_types]:
            matched_criteria += 1
            bonuses.append(f"Tipo: {prop_type}")
        elif prop_type:
            penalties.append(f"Tipo {prop_type} nao esta nas preferencias")

    # --- Tipo de oportunidade ---
    pref_opp_types = prefs.get("opportunity_types") or []
    if pref_opp_types:
        total_criteria += 1
        opp_type = _get(opp, "opportunity_type")
        if opp_type and opp_type in pref_opp_types:
            matched_criteria += 1
            bonuses.append(f"Oportunidade: {opp_type}")
        elif opp_type:
            penalties.append(f"Tipo de oportunidade {opp_type} nao preferido")

    # --- Localizacao (include) ---
    pref_locs_include = prefs.get("locations_include") or []
    if pref_locs_include:
        total_criteria += 1
        municipality = _get(opp, "municipality")
        if municipality and municipality.lower() in [l.lower() for l in pref_locs_include]:
            matched_criteria += 1
            bonuses.append(f"Localizacao: {municipality}")
        elif municipality:
            penalties.append(f"{municipality} nao esta nas localizacoes preferidas")

    # --- Localizacao (exclude) ---
    pref_locs_exclude = prefs.get("locations_exclude") or []
    if pref_locs_exclude:
        municipality = _get(opp, "municipality")
        if municipality and municipality.lower() in [l.lower() for l in pref_locs_exclude]:
            penalties.append(f"{municipality} esta na lista de exclusao")

    # --- Preco ---
    price = _get(opp, "price_mentioned") or _get(opp, "price")
    price_min = prefs.get("price_min")
    price_max = prefs.get("price_max")
    if price_min is not None or price_max is not None:
        total_criteria += 1
        if price:
            in_range = True
            if price_min and price < price_min:
                in_range = False
                penalties.append(f"Preco {price:,.0f} abaixo do minimo {price_min:,.0f}")
            if price_max and price > price_max:
                in_range = False
                penalties.append(f"Preco {price:,.0f} acima do maximo {price_max:,.0f}")
            if in_range:
                matched_criteria += 1
                bonuses.append(f"Preco dentro do range")

    # --- Area ---
    area = _get(opp, "area_m2")
    area_min = prefs.get("area_min")
    area_max = prefs.get("area_max")
    if area_min is not None or area_max is not None:
        total_criteria += 1
        if area:
            in_range = True
            if area_min and area < area_min:
                in_range = False
                penalties.append(f"Area {area}m2 abaixo do minimo {area_min}m2")
            if area_max and area > area_max:
                in_range = False
                penalties.append(f"Area {area}m2 acima do maximo {area_max}m2")
            if in_range:
                matched_criteria += 1
                bonuses.append("Area dentro do range")

    # --- Quartos ---
    bedrooms = _get(opp, "bedrooms")
    bed_min = prefs.get("bedrooms_min")
    bed_max = prefs.get("bedrooms_max")
    if bed_min is not None or bed_max is not None:
        total_criteria += 1
        if bedrooms is not None:
            in_range = True
            if bed_min is not None and bedrooms < bed_min:
                in_range = False
                penalties.append(f"T{bedrooms} abaixo do minimo T{bed_min}")
            if bed_max is not None and bedrooms > bed_max:
                in_range = False
                penalties.append(f"T{bedrooms} acima do maximo T{bed_max}")
            if in_range:
                matched_criteria += 1
                bonuses.append(f"Quartos T{bedrooms} dentro do range")

    # --- Preco vs mercado ---
    max_pvm = prefs.get("max_price_vs_market_pct")
    if max_pvm is not None and market_data:
        total_criteria += 1
        pvm = _get(market_data, "price_vs_market_pct")
        if pvm is not None:
            if pvm <= max_pvm:
                matched_criteria += 1
                bonuses.append(f"Preco {pvm:.0f}% do mercado (limite: {max_pvm}%)")
            else:
                penalties.append(f"Preco {pvm:.0f}% do mercado (acima do limite {max_pvm}%)")

    # --- Yield ---
    min_yield = prefs.get("min_yield_pct")
    if min_yield is not None and market_data:
        total_criteria += 1
        gross_yield = _get(market_data, "gross_yield_pct")
        if gross_yield is not None:
            if gross_yield >= min_yield:
                matched_criteria += 1
                bonuses.append(f"Yield {gross_yield:.1f}% (minimo: {min_yield}%)")
            else:
                penalties.append(f"Yield {gross_yield:.1f}% abaixo do minimo {min_yield}%")

    # Calcular percentagem
    if total_criteria == 0:
        match_pct = 50  # sem preferencias definidas
        match_label = "Sem preferencias definidas"
    else:
        match_pct = round(matched_criteria / total_criteria * 100)
        if match_pct >= 80:
            match_label = "Excelente match"
        elif match_pct >= 60:
            match_label = "Bom match"
        elif match_pct >= 40:
            match_label = "Match parcial"
        else:
            match_label = "Fora do perfil"

    return {
        "match_pct": match_pct,
        "match_label": match_label,
        "matched": matched_criteria,
        "total": total_criteria,
        "bonuses": bonuses,
        "penalties": penalties,
    }
