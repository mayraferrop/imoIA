"""M7 — Idiomas suportados e especificacoes de canais de marketing."""

from __future__ import annotations

from typing import Any, Dict

# ---------------------------------------------------------------------------
# Idiomas suportados
# ---------------------------------------------------------------------------

SUPPORTED_LANGUAGES: Dict[str, Dict[str, Any]] = {
    "pt-PT": {
        "label": "Português (Portugal)",
        "flag": "🇵🇹",
        "locale": "pt-PT",
        "field_suffix": "pt",
        "claude_instruction": (
            "Escreve em Português de Portugal (PT-PT) com tom profissional e rigoroso. "
            "Utiliza o vocabulário e ortografia corretos para Portugal: 'casa de banho' (nunca 'banheiro'), "
            "'renovado'/'remodelado' (nunca 'reformado'), 'andar' em vez de 'apartamento' no sentido informal, "
            "'estacionamento' (nunca 'garagem' como sinónimo genérico), 'elevador', 'moradia', 'fração'. "
            "Segue o Acordo Ortográfico de 1990. Usa o sistema métrico (m², metros). "
            "O público-alvo são investidores e compradores portugueses sofisticados. "
            "Destaca atributos como localização, potencial de valorização, rendimento líquido e qualidade de construção. "
            "Evita superlativos excessivos; privilegia factos concretos e linguagem clara e direta. "
            "Formata preços no estilo português: 250.000 € ou 250 000 €. "
            "Quando relevante, menciona regime de arrendamento, rendimento bruto e yield estimado."
        ),
    },
    "pt-BR": {
        "label": "Português (Brasil)",
        "flag": "🇧🇷",
        "locale": "pt-BR",
        "field_suffix": "pt_br",
        "claude_instruction": (
            "Escreve em Português do Brasil (PT-BR) com tom dinâmico e orientado ao investidor. "
            "Utiliza o vocabulário brasileiro: 'banheiro' (não 'casa de banho'), 'reformado' (não 'renovado'), "
            "'apartamento', 'metrô', 'garagem', 'sala de estar', 'varanda'. "
            "O público-alvo são investidores brasileiros interessados em Portugal como destino de investimento. "
            "Destaca sempre o programa Golden Visa (Visto Gold) quando a propriedade se qualifica — "
            "enfatiza o acesso à União Europeia, residência, e potencial de naturalização em 5 anos. "
            "Menciona a facilidade de financiamento bancário em Portugal para não residentes. "
            "Compara o custo por m² com as principais cidades brasileiras (São Paulo, Rio de Janeiro) "
            "para contextualizar o valor. "
            "Formata preços em euros com equivalência aproximada em reais quando útil. "
            "Tom entusiasmado mas credível; usa dados e percentagens de rentabilidade sempre que possível. "
            "Destaca a estabilidade jurídica, segurança e qualidade de vida em Portugal."
        ),
    },
    "en": {
        "label": "English",
        "flag": "🇬🇧",
        "locale": "en",
        "field_suffix": "en",
        "claude_instruction": (
            "Write in British English with a clear, professional and ROI-focused tone. "
            "Use British spelling and vocabulary: 'metre' (not 'meter'), 'colour', 'neighbourhood', "
            "'flat' (for apartment), 'bathroom', 'refurbished', 'freehold'/'leasehold' where applicable. "
            "Target audience is English-speaking expats, international investors and high-net-worth individuals "
            "looking at Portugal as an investment or relocation destination. "
            "Always include square footage (sq ft) alongside square metres (m²) for Anglo-American readers — "
            "use the conversion 1 m² = 10.764 sq ft. "
            "Emphasise ROI, net yield, capital appreciation potential and rental income. "
            "Mention the Non-Habitual Resident (NHR) tax regime and Golden Visa programme where relevant. "
            "Highlight proximity to international schools, airports and expat communities when applicable. "
            "Format prices in euros (€) with approximate GBP (£) equivalent if helpful. "
            "Keep sentences concise; avoid unnecessary jargon. Lead with the strongest investment case."
        ),
    },
    "fr": {
        "label": "Français",
        "flag": "🇫🇷",
        "locale": "fr",
        "field_suffix": "fr",
        "claude_instruction": (
            "Rédigez en français avec un ton formel et élégant, en utilisant systématiquement "
            "le vouvoiement ('vous'). "
            "Ciblez des acquéreurs et investisseurs français à la recherche d'une résidence secondaire, "
            "d'un pied-à-terre ou d'un investissement locatif au Portugal. "
            "Mettez en avant le style de vie : la douceur du climat, la gastronomie, la culture, "
            "la proximité de la France (vols directs), et la qualité de vie exceptionnelle. "
            "Évoquez la stabilité politique et juridique du Portugal au sein de l'Union Européenne. "
            "Mentionnez le régime fiscal des Résidents Non Habituels (RNH) et le Golden Visa si pertinent. "
            "Utilisez le système métrique (m²). Formatez les prix en euros (ex. : 250 000 €). "
            "Adoptez un registre soigné, sans vulgarité ni excès d'anglicismes. "
            "Privilégiez les descriptions évocatrices qui font rêver tout en restant factuelles. "
            "Pour les biens de prestige, insistez sur l'exclusivité, le cachet et le potentiel patrimonial."
        ),
    },
    "zh": {
        "label": "中文",
        "flag": "🇨🇳",
        "locale": "zh",
        "field_suffix": "zh",
        "claude_instruction": (
            "请用简体中文撰写内容，面向中国大陆及东南亚华人投资者。"
            "重点突出投资回报率（ROI）、净租金收益率以及资产增值潜力。"
            "务必详细介绍葡萄牙黄金签证（Golden Visa）计划：投资门槛、欧盟居留权、"
            "5年后申请葡萄牙/欧盟国籍的路径，以及子女教育优势。"
            "价格须同时标注欧元（€）和人民币（CNY）等值，并注明当前汇率基准。"
            "同时提供每平方米价格（€/m² 及 CNY/m²），便于与国内城市横向比较。"
            "提及葡萄牙的政治稳定性、欧盟法律框架、高质量医疗与教育体系。"
            "语言简洁专业，避免过于口语化。适当使用数据和百分比增强说服力。"
            "如适用，可对比上海、北京、深圳的房价，突显葡萄牙物业的价格优势。"
            "强调非惯常居民税务制度（NHR）对高收入人群的税务优惠。"
        ),
    },
}


# ---------------------------------------------------------------------------
# Especificações de canais
# ---------------------------------------------------------------------------

CHANNEL_SPECS: Dict[str, Dict[str, Any]] = {
    "website": {
        "label": "Website / Blog",
        "max_chars": 3000,
        "max_words": 500,
        "supports_html": True,
        "supports_images": True,
        "max_images": 20,
        "supports_video": True,
        "instruction": (
            "Cria uma descrição completa para página de imóvel em website. "
            "Inclui: título SEO apelativo, descrição longa estruturada com parágrafos, "
            "lista de características principais (bullet points), localização e acessos, "
            "potencial de investimento e rendimento estimado. "
            "Optimiza para SEO com keywords naturais (tipo de imóvel, localização, características). "
            "Usa formatação HTML básica: <h2>, <p>, <ul>, <strong>. "
            "Tom informativo, profissional e persuasivo."
        ),
    },
    "instagram_post": {
        "label": "Instagram — Post (Feed)",
        "max_chars": 2200,
        "max_hashtags": 30,
        "recommended_hashtags": 10,
        "supports_images": True,
        "max_images": 10,
        "supports_video": True,
        "max_video_seconds": 60,
        "instruction": (
            "Cria uma legenda para post de feed do Instagram. "
            "Começa com uma frase de impacto (hook) nas primeiras 2 linhas — é o que aparece antes do 'ver mais'. "
            "Desenvolve a descrição de forma envolvente com emojis estratégicos (não excessivos). "
            "Termina com call-to-action claro (ex.: 'Link na bio', 'Envia DM para mais informações'). "
            "Adiciona 8 a 12 hashtags relevantes no final (mistura de gerais e específicas). "
            "Tom aspiracional mas credível; foca na emoção e estilo de vida associados ao imóvel."
        ),
    },
    "instagram_story": {
        "label": "Instagram — Story",
        "max_chars": 150,
        "supports_images": True,
        "max_images": 1,
        "supports_video": True,
        "max_video_seconds": 15,
        "supports_stickers": True,
        "instruction": (
            "Cria texto muito curto e impactante para Story do Instagram (máx. 150 caracteres visíveis). "
            "Usa 1 a 3 emojis no máximo. Mensagem directa ao ponto — um único benefício ou facto chave. "
            "Inclui sugestão de call-to-action com sticker (ex.: 'Desliza para cima', 'Responde aqui'). "
            "Tom urgente ou curioso para maximizar engagement. "
            "Pensa visualmente: o texto deve complementar a imagem, não descrevê-la."
        ),
    },
    "facebook_post": {
        "label": "Facebook — Post",
        "max_chars": 63206,
        "recommended_chars": 400,
        "max_hashtags": 5,
        "supports_images": True,
        "max_images": 10,
        "supports_video": True,
        "instruction": (
            "Cria um post para Facebook com extensão média (200–400 caracteres recomendados). "
            "Tom mais informativo e menos visual que o Instagram — o público é tipicamente mais velho (35-60 anos). "
            "Inclui detalhes concretos: área, divisões, preço, localização, características únicas. "
            "Pode usar quebras de linha para legibilidade. Máximo 3–5 hashtags discretos no final. "
            "Call-to-action claro: comentar, enviar mensagem ou clicar no link. "
            "Pode incluir pergunta retórica para estimular comentários."
        ),
    },
    "facebook_group": {
        "label": "Facebook — Grupo Imobiliário",
        "max_chars": 63206,
        "recommended_chars": 600,
        "max_hashtags": 3,
        "supports_images": True,
        "max_images": 10,
        "instruction": (
            "Cria uma publicação detalhada para grupos imobiliários no Facebook. "
            "O público são profissionais do sector (agentes, investidores, consultores). "
            "Tom técnico e factual: área, tipologia, preço, rendimento estimado, estado de conservação, "
            "referência de registo/licença se disponível. "
            "Estrutura clara: título em maiúsculas, dados do imóvel em lista, contacto no final. "
            "Menciona se é off-market, exclusivo ou urgente. "
            "Evita excessos de emojis; usa no máximo 2–3 hashtags profissionais."
        ),
    },
    "linkedin": {
        "label": "LinkedIn",
        "max_chars": 3000,
        "recommended_chars": 1300,
        "max_hashtags": 5,
        "supports_images": True,
        "max_images": 9,
        "supports_video": True,
        "instruction": (
            "Cria um artigo/post para LinkedIn com tom profissional e orientado ao investimento. "
            "Público-alvo: investidores, empresários, profissionais de finanças e imobiliário. "
            "Enquadra a oportunidade no contexto do mercado imobiliário português — tendências, yields, valorização. "
            "Inclui dados financeiros: preço/m², yield estimado, potencial de valorização, custos de aquisição. "
            "Pode estruturar com subtítulos implícitos usando emojis ou separadores (ex.: '▸'). "
            "Termina com 3–5 hashtags profissionais (ex.: #InvestimentoImobiliário #Portugal #RealEstate). "
            "Pode incluir call-to-action para contacto directo ou reunião."
        ),
    },
    "tiktok": {
        "label": "TikTok",
        "max_chars": 2200,
        "recommended_chars": 300,
        "max_hashtags": 10,
        "supports_video": True,
        "max_video_seconds": 180,
        "supports_images": True,
        "instruction": (
            "Cria texto/legenda para TikTok com estilo jovem, dinâmico e directo. "
            "Público mais jovem (25–40) com interesse em investimento imobiliário e finanças pessoais. "
            "Começa com hook forte nas primeiras palavras — tem de captar atenção em 2 segundos. "
            "Usa linguagem descontraída mas informativa. Emojis são bem-vindos e naturais. "
            "Menciona factos surpreendentes ou números impactantes (ex.: 'yield de 6% no centro de Lisboa'). "
            "Inclui 5–10 hashtags misturando trending (#realestate #investimento #Portugal) e específicos. "
            "Sugere texto para o vídeo (overlay text) se aplicável: frases curtas e impactantes para o ecrã."
        ),
    },
    "whatsapp": {
        "label": "WhatsApp",
        "max_chars": 4096,
        "recommended_chars": 500,
        "supports_images": True,
        "supports_video": True,
        "supports_bold": True,
        "supports_italic": True,
        "instruction": (
            "Cria uma mensagem para partilha via WhatsApp (grupo ou individual). "
            "Tom directo, pessoal e eficiente — quem recebe lê no telemóvel. "
            "Usa formatação WhatsApp: *negrito* para títulos e dados chave, _itálico_ para detalhes secundários. "
            "Estrutura: introdução curta → dados do imóvel → preço → call-to-action (contacto, visita, link). "
            "Sem hashtags. Emojis com moderação para dividir secções (ex.: 🏠 📍 💶 📞). "
            "Máximo 300–500 caracteres para mensagem simples; até 1000 para ficha técnica completa. "
            "Termina sempre com uma forma de contacto ou link directo."
        ),
    },
    "portal": {
        "label": "Portal Imobiliário (Idealista / Imovirtual / OLX)",
        "max_chars": 4000,
        "recommended_chars": 800,
        "supports_images": True,
        "max_images": 50,
        "supports_html": False,
        "instruction": (
            "Cria uma descrição para portal imobiliário (Idealista, Imovirtual, OLX, Casa Sapo). "
            "Tom profissional, factual e completo — o comprador está em modo de pesquisa activa. "
            "Estrutura recomendada: "
            "1) Frase de abertura com tipo, localização e característica diferenciadora; "
            "2) Descrição detalhada do imóvel (divisões, áreas, estado, orientação solar, vistas); "
            "3) Características técnicas (aquecimento, janelas, estacionamento, arrecadação); "
            "4) Localização e acessos (transportes, escolas, comércio, distâncias); "
            "5) Potencial/enquadramento (arrendamento, habitação própria, investimento); "
            "6) Contacto e próximos passos. "
            "Sem formatação HTML. Usa parágrafos separados por linha em branco. "
            "Inclui todas as informações relevantes sem repetição."
        ),
    },
    "email": {
        "label": "E-mail / Newsletter",
        "max_chars": 10000,
        "recommended_chars": 600,
        "supports_html": True,
        "supports_images": True,
        "instruction": (
            "Cria um e-mail de apresentação de imóvel para envio a lista de contactos/investidores. "
            "Estrutura: assunto apelativo (max 60 caracteres, sem spam words), "
            "preheader text (40–90 caracteres), corpo do e-mail. "
            "Corpo: cumprimento personalizado → proposta de valor em 2–3 frases → "
            "destaques do imóvel (lista bullet com 4–6 pontos) → "
            "dados financeiros chave (preço, yield, área) → "
            "call-to-action principal (botão/link para ficha completa ou agendamento de visita) → "
            "assinatura profissional. "
            "Tom personalizado e exclusivo — o destinatário deve sentir que recebeu uma oportunidade seleccionada para si. "
            "Pode usar HTML básico para formatação: <h2>, <p>, <ul>, <strong>, <a>. "
            "Optimiza para mobile: parágrafos curtos, botão CTA com destaque visual."
        ),
    },
}
