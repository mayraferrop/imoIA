"""M2 — Analista de mercado.

Integra CASAFARI API (95M+ listagens, 20+ paises) e INE para fornecer
dados de mercado automatizados: comparaveis, avaliacoes, series temporais e alertas.

Alimenta todos os outros modulos:
- M1 (Ingestor): enriquece oportunidades com preco/m2 da zona
- M3 (Financeiro): fornece ARV via comparaveis reais
- M4 (Deal Pipeline): valida preco de compra vs mercado
- M5 (Due Diligence): dados de mercado para avaliacao
- M7 (Marketing): preco de listagem baseado em comparaveis
"""
