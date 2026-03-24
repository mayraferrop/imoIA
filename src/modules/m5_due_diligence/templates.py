"""
Modelos de checklists para due diligence imobiliária.

Contém templates base para Portugal e Brasil, com extensões por tipo de propriedade
e estratégia de investimento.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Portugal — Checklist Base
# ---------------------------------------------------------------------------

PT_BASE_CHECKLIST: list[dict] = [
    # --- Registos ---
    {
        "category": "registos",
        "item_key": "certidao_predial",
        "item_name": "Certidão Predial Permanente",
        "description": (
            "Obter a certidão predial permanente do imóvel na Conservatória do Registo Predial. "
            "Verificar titular(es), ónus, encargos, hipotecas, penhoras e quaisquer anotações. "
            "Confirmar que a descrição predial corresponde ao imóvel em análise."
        ),
        "is_required": True,
        "sort_order": 10,
        "cost": 20.0,
        "expiry_days": 180,
        "red_flag_checks": [
            "hipoteca_ativa",
            "penhora_registada",
            "outros_onus",
            "titular_divergente",
        ],
    },
    {
        "category": "registos",
        "item_key": "caderneta_predial",
        "item_name": "Caderneta Predial Urbana",
        "description": (
            "Solicitar a caderneta predial urbana nas Finanças (Portal das Finanças ou presencialmente). "
            "Verificar o valor patrimonial tributário (VPT), a afectação, a área bruta de construção, "
            "área do terreno e fracção autónoma (se aplicável). Confirmar coerência com o registo predial."
        ),
        "is_required": True,
        "sort_order": 20,
        "cost": 0.0,
        "expiry_days": 365,
        "red_flag_checks": [
            "vpt_divergente_do_preco",
            "afectacao_incorreta",
            "area_divergente",
        ],
    },
    {
        "category": "registos",
        "item_key": "certificado_energetico",
        "item_name": "Certificado Energético",
        "description": (
            "Confirmar a existência de certificado energético válido emitido pela ADENE. "
            "Verificar a classe energética (A+ a F), identificar medidas de melhoria sugeridas "
            "e avaliar o impacto no custo de obra de reabilitação. Certificado obrigatório para "
            "venda e arrendamento."
        ),
        "is_required": True,
        "sort_order": 30,
        "cost": 250.0,
        "expiry_days": 3650,
        "red_flag_checks": [
            "classe_energetica_f",
            "certificado_expirado",
            "ausencia_certificado",
        ],
    },
    # --- Fiscal ---
    {
        "category": "fiscal",
        "item_key": "dividas_imi",
        "item_name": "Verificação de Dívidas de IMI",
        "description": (
            "Obter junto das Finanças a certidão de não dívida referente ao Imposto Municipal sobre "
            "Imóveis (IMI). Verificar se existem colectas em dívida de anos anteriores. "
            "As dívidas de IMI acompanham o imóvel e transitam para o comprador."
        ),
        "is_required": True,
        "sort_order": 40,
        "cost": 15.0,
        "expiry_days": 90,
        "red_flag_checks": [
            "divida_imi_ativa",
            "execucao_fiscal_pendente",
        ],
    },
    {
        "category": "fiscal",
        "item_key": "simulacao_imt",
        "item_name": "Simulação de IMT e Imposto de Selo",
        "description": (
            "Realizar simulação do Imposto Municipal sobre Transmissões Onerosas (IMT) e do "
            "Imposto de Selo (0,8%) com base no preço de aquisição ou VPT (o maior). "
            "Aplicar tabelas OE2026 (Lei 73-A/2025). Verificar elegibilidade para isenções "
            "(reabilitação urbana, habitação própria permanente). Incluir no mapa de custos."
        ),
        "is_required": True,
        "sort_order": 50,
        "red_flag_checks": [
            "imt_superior_ao_estimado",
            "isencao_nao_aplicavel",
        ],
    },
    # --- Licenciamento ---
    {
        "category": "licenciamento",
        "item_key": "licenca_utilizacao",
        "item_name": "Licença de Utilização",
        "description": (
            "Verificar junto da Câmara Municipal a existência de licença de utilização válida "
            "para o fim pretendido (habitacional, comercial, misto). Imóveis construídos antes "
            "de 7 de Agosto de 1951 estão isentos. Ausência de licença impede a escritura "
            "e o financiamento bancário."
        ),
        "is_required": True,
        "sort_order": 60,
        "cost": 30.0,
        "expiry_days": None,
        "red_flag_checks": [
            "licenca_ausente",
            "licenca_para_fim_diferente",
            "obra_sem_licenca_detectada",
        ],
    },
    {
        "category": "licenciamento",
        "item_key": "ficha_tecnica",
        "item_name": "Ficha Técnica da Habitação",
        "description": (
            "Solicitar a Ficha Técnica da Habitação (FTH) para imóveis habitacionais construídos "
            "ou sujeitos a obras após 30 de Março de 2004. Documento disponível na Câmara Municipal "
            "ou com o proprietário. Descreve as características técnicas e materiais construtivos."
        ),
        "is_required": False,
        "sort_order": 70,
        "red_flag_checks": [
            "ficha_tecnica_ausente_pos_2004",
            "divergencia_com_realidade",
        ],
    },
    # --- Condomínio ---
    {
        "category": "condominio",
        "item_key": "dividas_condominio",
        "item_name": "Declaração de Não Dívida ao Condomínio",
        "description": (
            "Obter junto do administrador do condomínio declaração escrita confirmando que a fracção "
            "não tem quotas em dívida, nem contribuições extraordinárias pendentes. "
            "As dívidas ao condomínio acompanham o imóvel. Verificar também obras aprovadas "
            "em assembleia ainda não executadas que possam gerar encargos futuros."
        ),
        "is_required": True,
        "sort_order": 80,
        "red_flag_checks": [
            "divida_condominio_ativa",
            "obras_aprovadas_por_pagar",
        ],
    },
    {
        "category": "condominio",
        "item_key": "actas_condominio",
        "item_name": "Actas das Assembleias de Condomínio (últimos 3 anos)",
        "description": (
            "Solicitar ao administrador do condomínio as actas das últimas três assembleias gerais. "
            "Identificar obras aprovadas ou em discussão, conflitos entre condóminos, "
            "situação do fundo de reserva e quaisquer decisões que possam afectar o valor "
            "ou a utilização da fracção."
        ),
        "is_required": True,
        "sort_order": 90,
        "red_flag_checks": [
            "obras_estruturais_aprovadas",
            "fundo_reserva_insuficiente",
            "litigios_condominiais",
        ],
    },
    # --- Serviços ---
    {
        "category": "servicos",
        "item_key": "dividas_servicos",
        "item_name": "Verificação de Dívidas a Serviços Públicos",
        "description": (
            "Confirmar junto dos fornecedores de água, gás e electricidade que não existem "
            "dívidas associadas ao imóvel ou ao contador. Solicitar ao vendedor a apresentação "
            "das últimas facturas pagas. Verificar se os contadores estão activos e em nome correcto."
        ),
        "is_required": True,
        "sort_order": 100,
        "red_flag_checks": [
            "contador_cortado",
            "divida_servicos_ativa",
        ],
    },
    # --- Urbano ---
    {
        "category": "urbano",
        "item_key": "pdm_verificacao",
        "item_name": "Verificação no PDM (Plano Director Municipal)",
        "description": (
            "Consultar o PDM do município na Câmara Municipal ou via plataforma SNIT/SNITURB. "
            "Confirmar a qualificação do solo (urbano, urbanizável, rústico), a classe de espaço, "
            "os índices urbanísticos aplicáveis e as condicionantes (REN, RAN, servidões). "
            "Relevante para avaliar potencial de construção ou ampliação."
        ),
        "is_required": True,
        "sort_order": 110,
        "red_flag_checks": [
            "solo_rustico",
            "servidao_limitante",
            "indice_construtibilidade_baixo",
        ],
    },
    {
        "category": "urbano",
        "item_key": "aru_verificacao",
        "item_name": "Verificação de ARU (Área de Reabilitação Urbana)",
        "description": (
            "Confirmar se o imóvel se encontra numa Área de Reabilitação Urbana (ARU) delimitada. "
            "A inclusão em ARU pode permitir benefícios fiscais (isenção de IMI, redução de IMT, "
            "IVA a 6% em obras) e acesso a apoios IHRU. Verificar junto da Câmara Municipal "
            "ou via portal da DGTERRITÓRIO."
        ),
        "is_required": True,
        "sort_order": 120,
        "red_flag_checks": [
            "fora_aru_sem_beneficios",
        ],
    },
    {
        "category": "urbano",
        "item_key": "classificacao_patrimonial",
        "item_name": "Verificação de Classificação Patrimonial",
        "description": (
            "Verificar junto da DGPC (Direção-Geral do Património Cultural) ou da Câmara Municipal "
            "se o imóvel ou a área envolvente tem classificação patrimonial (Monumento Nacional, "
            "Imóvel de Interesse Público, etc.). A classificação pode impor restrições severas "
            "a obras de remodelação e alteração da fachada."
        ),
        "is_required": True,
        "sort_order": 130,
        "red_flag_checks": [
            "classificacao_patrimonial_ativa",
            "zona_de_protecao",
        ],
    },
    # --- Técnico ---
    {
        "category": "tecnico",
        "item_key": "vistoria_imovel",
        "item_name": "Vistoria Técnica ao Imóvel",
        "description": (
            "Realizar vistoria presencial detalhada ao imóvel com técnico qualificado (engenheiro "
            "ou arquitecto). Avaliar estado da estrutura, cobertura, instalações eléctricas e "
            "canalizações, humidades, infiltrações, isolamentos e anomalias construtivas. "
            "Elaborar relatório técnico com estimativa de custo de obra necessária."
        ),
        "is_required": True,
        "sort_order": 140,
        "cost": 500.0,
        "red_flag_checks": [
            "problemas_estruturais",
            "amianto_detectado",
            "humidades_graves",
            "instalacoes_em_mau_estado",
        ],
    },
]


# ---------------------------------------------------------------------------
# Portugal — Extras por Tipo de Propriedade
# ---------------------------------------------------------------------------

PT_EXTRA_BY_TYPE: dict[str, list[dict]] = {
    "predio": [
        {
            "category": "registos",
            "item_key": "propriedade_horizontal",
            "item_name": "Título Constitutivo da Propriedade Horizontal",
            "description": (
                "Obter o título constitutivo da propriedade horizontal (escritura ou deliberação judicial). "
                "Verificar a descrição de cada fracção autónoma, permilagem, partes comuns e regulamento "
                "do condomínio. Confirmar correspondência com a realidade física do edifício."
            ),
            "is_required": True,
            "sort_order": 145,
            "red_flag_checks": [
                "titulo_nao_constituido",
                "permilagem_incorreta",
                "fraccoes_nao_registadas",
            ],
        },
        {
            "category": "registos",
            "item_key": "certidao_predial_fraccoes",
            "item_name": "Certidões Prediais de Todas as Fracções",
            "description": (
                "Obter certidão predial permanente individualizada para cada fracção autónoma do prédio. "
                "Verificar ónus, encargos e titularidade de cada fracção separadamente. "
                "Identificar fracções com arrendatários com direito de preferência na compra."
            ),
            "is_required": True,
            "sort_order": 150,
            "cost": 20.0,
            "expiry_days": 180,
            "red_flag_checks": [
                "fraccao_com_onus_individual",
                "arrendatario_com_preferencia",
                "fraccao_penhorada",
            ],
        },
    ],
    "terreno": [
        {
            "category": "urbano",
            "item_key": "viabilidade_construcao",
            "item_name": "Certidão de Viabilidade Construtiva",
            "description": (
                "Solicitar à Câmara Municipal informação prévia sobre a viabilidade de construção "
                "no terreno. Obter os parâmetros urbanísticos aplicáveis: índice de utilização, "
                "índice de ocupação, cércea máxima, afastamentos e número máximo de fogos. "
                "Fundamental para avaliar o potencial de desenvolvimento."
            ),
            "is_required": True,
            "sort_order": 145,
            "cost": 100.0,
            "expiry_days": 365,
            "red_flag_checks": [
                "construcao_nao_viavel",
                "restricoes_severas",
                "solo_nao_urbanizavel",
            ],
        },
        {
            "category": "tecnico",
            "item_key": "topografia",
            "item_name": "Levantamento Topográfico",
            "description": (
                "Encomendar levantamento topográfico do terreno a técnico habilitado. "
                "Confirmar limites, área real, curvas de nível, acessos existentes e infraestruturas "
                "disponíveis (água, esgotos, electricidade). Verificar concordância com a certidão predial."
            ),
            "is_required": True,
            "sort_order": 155,
            "cost": 800.0,
            "red_flag_checks": [
                "area_real_inferior",
                "limite_em_litigio",
                "sem_acesso_publico",
            ],
        },
        {
            "category": "urbano",
            "item_key": "ren_ran",
            "item_name": "Verificação de REN e RAN",
            "description": (
                "Verificar se o terreno ou parte dele se encontra abrangido pela Reserva Ecológica "
                "Nacional (REN) ou pela Reserva Agrícola Nacional (RAN). A inclusão nestas reservas "
                "condiciona fortemente a edificabilidade. Consultar carta de condicionantes do PDM "
                "e plataforma SNIT."
            ),
            "is_required": True,
            "sort_order": 160,
            "red_flag_checks": [
                "terreno_em_ren",
                "terreno_em_ran",
                "area_parcial_condicionada",
            ],
        },
    ],
    "moradia": [
        {
            "category": "registos",
            "item_key": "limites_propriedade",
            "item_name": "Confirmação dos Limites da Propriedade",
            "description": (
                "Verificar in loco os limites físicos da propriedade (muros, vedações, marcos) "
                "e confrontar com a certidão predial e caderneta. Confirmar que não existem "
                "invasões de propriedades vizinhas nem disputas de limites. "
                "Em caso de dúvida, encomendar levantamento topográfico."
            ),
            "is_required": True,
            "sort_order": 145,
            "red_flag_checks": [
                "limite_em_litigio",
                "area_real_inferior",
                "invasao_detectada",
            ],
        },
    ],
}


# ---------------------------------------------------------------------------
# Portugal — Extras por Estratégia de Investimento
# ---------------------------------------------------------------------------

PT_EXTRA_BY_STRATEGY: dict[str, list[dict]] = {
    "fix_and_flip": [
        {
            "category": "licenciamento",
            "item_key": "comunicacao_previa",
            "item_name": "Comunicação Prévia / Pedido de Informação Prévia para Obras",
            "description": (
                "Verificar junto da Câmara Municipal os requisitos para licenciamento das obras "
                "de reabilitação previstas. Determinar se é necessário processo de licenciamento "
                "completo, comunicação prévia ou se as obras são isentas. "
                "Avaliar prazos e custos de licenciamento no plano de negócio."
            ),
            "is_required": True,
            "sort_order": 200,
            "cost": 500.0,
            "red_flag_checks": [
                "obras_sujeitas_a_licenciamento_complexo",
                "prazo_licenciamento_longo",
                "restricoes_por_classificacao",
            ],
        },
    ],
    "buy_and_hold": [
        {
            "category": "licenciamento",
            "item_key": "licenca_arrendamento",
            "item_name": "Verificação de Requisitos para Arrendamento",
            "description": (
                "Confirmar que o imóvel reúne as condições legais para arrendamento habitacional: "
                "licença de utilização para habitação, condições mínimas de habitabilidade "
                "(NRAU e portaria de habitação digna), e ausência de impedimentos legais. "
                "Verificar eventuais arrendamentos existentes e direitos dos inquilinos."
            ),
            "is_required": True,
            "sort_order": 200,
            "red_flag_checks": [
                "arrendatario_existente",
                "contrato_arrendamento_antigo",
                "condicoes_habitabilidade_insuficientes",
            ],
        },
    ],
    "alojamento_local": [
        {
            "category": "licenciamento",
            "item_key": "licenca_al",
            "item_name": "Viabilidade de Licença de Alojamento Local",
            "description": (
                "Verificar junto da Câmara Municipal se é possível obter licença de Alojamento "
                "Local (AL) para o imóvel. Confirmar se a freguesia está sujeita a moratória "
                "ou suspensão de novas licenças AL. Verificar regulamento municipal de AL "
                "e requisitos do condomínio (oposição prevista no art.º 1422.º CC)."
            ),
            "is_required": True,
            "sort_order": 200,
            "red_flag_checks": [
                "moratoria_al_ativa",
                "condominio_oposto_al",
                "freguesia_restrita",
            ],
        },
    ],
    "desenvolvimento": [
        {
            "category": "licenciamento",
            "item_key": "projecto_arquitectura",
            "item_name": "Viabilidade de Projecto de Arquitectura",
            "description": (
                "Encomendar estudo de viabilidade arquitectónica antes de avançar com a aquisição. "
                "O arquitecto deve confirmar a viabilidade construtiva com base nos parâmetros "
                "urbanísticos do PDM, elaborar estimativa de área bruta de construção possível "
                "e identificar constrangimentos técnicos e regulamentares."
            ),
            "is_required": True,
            "sort_order": 200,
            "cost": 2000.0,
            "red_flag_checks": [
                "area_construcao_inferior_ao_previsto",
                "estudo_inviavel",
                "restricoes_arquitectonicas",
            ],
        },
    ],
    "wholesale": [
        {
            "category": "licenciamento",
            "item_key": "clausula_cessao",
            "item_name": "Cláusula de Cessão de Posição Contratual",
            "description": (
                "Assegurar que o contrato promessa de compra e venda (CPCV) inclui cláusula "
                "expressa que permite a cessão da posição contratual a terceiro. "
                "Verificar com advogado especializado a redacção da cláusula e as implicações "
                "fiscais da cessão (IMT sobre o valor da cedência). "
                "Confirmar que o vendedor aceita a cessão sem penalização."
            ),
            "is_required": True,
            "sort_order": 200,
            "red_flag_checks": [
                "clausula_cessao_ausente",
                "vendedor_recusa_cessao",
                "imt_cessao_nao_calculado",
            ],
        },
    ],
}


# ---------------------------------------------------------------------------
# Brasil — Checklist Base
# ---------------------------------------------------------------------------

BR_BASE_CHECKLIST: list[dict] = [
    {
        "category": "registos",
        "item_key": "matricula_atualizada",
        "item_name": "Matrícula Atualizada do Imóvel",
        "description": (
            "Obter a certidão de inteiro teor da matrícula do imóvel no Cartório de Registro de Imóveis "
            "competente, com data de expedição não superior a 30 dias. Verificar cadeia dominial, "
            "ônus reais (hipotecas, usufrutos, servidões), penhoras e averbações. "
            "Confirmar que o vendedor consta como proprietário registado."
        ),
        "is_required": True,
        "sort_order": 10,
        "cost": 50.0,
        "expiry_days": 30,
        "red_flag_checks": [
            "hipoteca_ativa",
            "penhora_registada",
            "proprietario_divergente",
            "cadeia_dominial_irregular",
        ],
    },
    {
        "category": "fiscal",
        "item_key": "iptu",
        "item_name": "Certidão de Débitos de IPTU",
        "description": (
            "Obter certidão negativa de débitos de IPTU (Imposto Predial e Territorial Urbano) "
            "junto à Prefeitura Municipal. Verificar exercícios em aberto dos últimos 5 anos. "
            "Os débitos de IPTU são propter rem e acompanham o imóvel, sendo transferidos ao comprador."
        ),
        "is_required": True,
        "sort_order": 20,
        "cost": 30.0,
        "expiry_days": 90,
        "red_flag_checks": [
            "debito_iptu_ativo",
            "execucao_fiscal_municipal",
        ],
    },
    {
        "category": "judicial",
        "item_key": "certidao_civel",
        "item_name": "Certidões de Ações Cíveis (Vendedor)",
        "description": (
            "Obter certidões de distribuição de ações cíveis em nome do vendedor nos últimos 10 anos, "
            "junto à Justiça Estadual e Federal da comarca do imóvel e do domicílio do vendedor. "
            "Verificar ações que possam resultar em penhora do imóvel ou fraude à execução."
        ),
        "is_required": True,
        "sort_order": 30,
        "cost": 40.0,
        "expiry_days": 30,
        "red_flag_checks": [
            "acao_civel_com_risco_penhora",
            "fraude_execucao_potencial",
        ],
    },
    {
        "category": "judicial",
        "item_key": "certidao_federal",
        "item_name": "Certidões de Débitos Federais e Ações na Justiça Federal",
        "description": (
            "Verificar junto à Receita Federal e à Procuradoria-Geral da Fazenda Nacional (PGFN) "
            "a existência de débitos tributários federais em nome do vendedor. "
            "Obter também certidão de distribuição de ações na Justiça Federal. "
            "Dívidas activas da União podem resultar em penhora de bens."
        ),
        "is_required": True,
        "sort_order": 40,
        "cost": 0.0,
        "expiry_days": 30,
        "red_flag_checks": [
            "debito_receita_federal",
            "inscricao_divida_ativa_uniao",
        ],
    },
    {
        "category": "judicial",
        "item_key": "certidao_trabalhista",
        "item_name": "Certidão de Débitos Trabalhistas (CNDT)",
        "description": (
            "Obter a Certidão Negativa de Débitos Trabalhistas (CNDT) emitida pelo TST "
            "em nome do vendedor (pessoa física ou jurídica). Dívidas trabalhistas podem resultar "
            "em penhora de bens do devedor, incluindo imóveis, mesmo após a venda "
            "se configurar fraude à execução."
        ),
        "is_required": True,
        "sort_order": 50,
        "cost": 0.0,
        "expiry_days": 30,
        "red_flag_checks": [
            "debito_trabalhista_ativo",
        ],
    },
    {
        "category": "judicial",
        "item_key": "certidao_inss_fgts",
        "item_name": "Certidão de Débitos do INSS e FGTS",
        "description": (
            "Verificar a existência de débitos previdenciários (INSS) e do FGTS em nome do vendedor, "
            "especialmente se pessoa jurídica ou empresário individual. "
            "Obter Certidão de Regularidade Fiscal (CRF) perante a Receita Federal/INSS "
            "e extrato de regularidade do FGTS junto à Caixa Económica Federal."
        ),
        "is_required": True,
        "sort_order": 60,
        "cost": 0.0,
        "expiry_days": 30,
        "red_flag_checks": [
            "debito_previdenciario_ativo",
            "debito_fgts_ativo",
        ],
    },
    {
        "category": "judicial",
        "item_key": "certidao_protesto",
        "item_name": "Certidão de Protesto de Títulos",
        "description": (
            "Obter certidão de protesto de títulos em nome do vendedor junto ao(s) Cartório(s) "
            "de Protesto da comarca de domicílio e da comarca do imóvel. "
            "Elevado volume de protestos pode indicar situação financeira precária do vendedor "
            "com risco de fraude à execução em transacção imobiliária futura."
        ),
        "is_required": True,
        "sort_order": 70,
        "cost": 25.0,
        "expiry_days": 30,
        "red_flag_checks": [
            "protestos_elevados",
            "protestos_recentes",
        ],
    },
]


# ---------------------------------------------------------------------------
# Função auxiliar
# ---------------------------------------------------------------------------

def get_checklist_template(
    country: str,
    property_type: str | None = None,
    strategy: str | None = None,
) -> list[dict]:
    """Constrói e devolve o template de checklist completo para os parâmetros dados.

    Começa com o template base do país indicado, adiciona os itens específicos
    por tipo de propriedade (apenas PT) e, por fim, os itens específicos por
    estratégia de investimento (apenas PT).

    Args:
        country: Código do país — ``"PT"`` (Portugal) ou ``"BR"`` (Brasil).
        property_type: Tipo de propriedade. Valores PT suportados:
            ``"predio"``, ``"terreno"``, ``"moradia"``.
        strategy: Estratégia de investimento. Valores PT suportados:
            ``"fix_and_flip"``, ``"buy_and_hold"``, ``"alojamento_local"``,
            ``"desenvolvimento"``, ``"wholesale"``.

    Returns:
        Lista de dicionários com todos os itens de due diligence aplicáveis,
        ordenada por ``sort_order``.

    Raises:
        ValueError: Se o código de país não for reconhecido.
    """
    country_upper = country.upper()

    if country_upper == "PT":
        items: list[dict] = list(PT_BASE_CHECKLIST)

        if property_type and property_type in PT_EXTRA_BY_TYPE:
            items.extend(PT_EXTRA_BY_TYPE[property_type])

        if strategy and strategy in PT_EXTRA_BY_STRATEGY:
            items.extend(PT_EXTRA_BY_STRATEGY[strategy])

    elif country_upper == "BR":
        items = list(BR_BASE_CHECKLIST)

    else:
        raise ValueError(
            f"País não suportado: {country!r}. "
            "Valores aceites: 'PT' (Portugal), 'BR' (Brasil)."
        )

    return sorted(items, key=lambda i: i["sort_order"])
