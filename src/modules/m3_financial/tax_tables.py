"""Tabelas fiscais actualizadas para Portugal (OE2026) e Brasil.

Separadas em ficheiro proprio para facil actualizacao anual.
Todos os valores em EUR (Portugal) ou BRL (Brasil).
"""

from __future__ import annotations

# ============================================================
# PORTUGAL — IMT 2026 (Lei 73-A/2025, Tabela III — Investimento)
# ============================================================
# Investimento/habitacao secundaria NAO tem escalao de isencao (0%).
# Formato: (limite_superior, taxa, parcela_a_abater)
# Para escaloes com parcela_a_abater=None, aplica-se taxa unica.

IMT_TABLE_PT_INVESTMENT: list[tuple[float, float, float | None]] = [
    (106_346, 0.01, 0),
    (145_470, 0.02, 1_063.46),
    (198_347, 0.05, 5_427.56),
    (330_539, 0.07, 9_394.50),
    (633_931, 0.08, 12_699.89),
    (1_150_853, 0.06, None),
    (float("inf"), 0.075, None),
]

IMT_TABLE_PT_HPP: list[tuple[float, float, float | None]] = [
    (104_261, 0.00, 0),
    (142_618, 0.02, 2_085.22),
    (194_462, 0.05, 6_363.74),
    (323_988, 0.07, 12_252.98),
    (633_931, 0.08, 15_492.86),
    (1_150_853, 0.06, None),
    (float("inf"), 0.075, None),
]

# Imposto de Selo
IMPOSTO_SELO_PCT = 0.008
IMPOSTO_SELO_ADICIONAL_THRESHOLD = 1_000_000

# Custos fixos estimados
CUSTOS_NOTARIO_REGISTO_PT = 725
CUSTOS_ADVOGADO_PCT_PT = 0.015

# Mais-valias PT
MAIS_VALIAS_INCLUSAO_PCT = 0.50

# Taxas progressivas IRS 2026
IRS_BRACKETS_PT_2026: list[tuple[float, float]] = [
    (7_703, 0.1325),
    (11_623, 0.18),
    (16_472, 0.23),
    (21_321, 0.26),
    (27_146, 0.3275),
    (39_791, 0.37),
    (51_997, 0.435),
    (81_199, 0.45),
    (float("inf"), 0.48),
]

COEF_DESVALORIZACAO_DEFAULT = 1.0

# ============================================================
# PORTUGAL — Credito Habitacao (referencias Q1 2026)
# ============================================================
EURIBOR_12M_REFERENCE = 0.0222
SPREAD_MIN_REFERENCE = 0.0070
SPREAD_TYPICAL_REFERENCE = 0.0110
LTV_MAX_INVESTMENT = 0.70
LTV_MAX_HPP = 0.90

# Custos bancarios tipicos
BANK_FEES_PT: dict[str, float] = {
    "dossier": 380,
    "avaliacao": 310,
    "registo_hipoteca": 200,
    "outros": 551,
    "is_pct": 0.006,
}

# ============================================================
# PORTUGAL — Holding costs (estimativas default)
# ============================================================
IMI_RATE_DEFAULT = 0.0035
VPT_ESTIMATE_PCT = 0.60
CONDOMINIO_DEFAULT_MONTHLY = 50
SEGURO_DEFAULT_ANNUAL = 300
CONSUMOS_DEFAULT_MONTHLY = 80

# ============================================================
# BRASIL — Impostos
# ============================================================
ITBI_DEFAULT_PCT = 0.03
ESCRITURA_REGISTRO_ESTIMATE_BRL = 5_000

IR_GAIN_BRACKETS_BR: list[tuple[float, float]] = [
    (5_000_000, 0.15),
    (10_000_000, 0.175),
    (30_000_000, 0.20),
    (float("inf"), 0.225),
]

ISENCAO_IMOVEL_UNICO_BRL = 440_000
PRAZO_REINVESTIMENTO_BR_DIAS = 180
