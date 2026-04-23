"""M1 Scraper — captação de listings de portais PT (Idealista, Imovirtual).

Pipeline:
1. Scraper fetch URL → lista de listings brutos (ScrapedListing)
2. Adapter converte para input do OpportunityClassifier (reaproveitando
   o classificador que já filtra mensagens WhatsApp pela estratégia activa)
3. Service persiste em `properties` com source='idealista_pt'|'imovirtual_pt',
   dedup por (source, source_external_id), e regista price_history nas mudanças

Só listings classificados como oportunidades (is_opportunity=true) entram
na tabela properties. Os restantes são descartados.
"""
