"""
Módulo de templates de marcos de obra para o M6 — Gestão de Obra.

Define listas de milestones pré-configuradas para os tipos de reabilitação
mais comuns em estratégias fix and flip, alojamento local e prédios inteiros.
"""

from __future__ import annotations


FLIP_STANDARD_MILESTONES: list[dict] = [
    {
        "name": "Demolição e remoção",
        "category": "estrutura",
        "description": (
            "Demolir paredes não estruturais, remover revestimentos antigos (azulejos, "
            "soalhos, estuques), desmontar instalações obsoletas e assegurar a limpeza "
            "total do espaço antes do início das especialidades. Reservar contentor de "
            "entulho e cumprir regulamentação municipal de transporte de resíduos."
        ),
        "sort_order": 1,
        "budget_pct": 5.0,
    },
    {
        "name": "Reforço estrutural",
        "category": "estrutura",
        "description": (
            "Avaliar e reforçar lajes, vigas e paredes estruturais conforme projecto de "
            "estabilidade. Incluir tratamento de fissuras, injecção de caldas de cimento "
            "onde necessário e verificação de conformidade com o RSAEEP. Obter aprovação "
            "do engenheiro estrutural antes de prosseguir."
        ),
        "sort_order": 2,
        "budget_pct": 10.0,
    },
    {
        "name": "Instalação eléctrica",
        "category": "instalacoes",
        "description": (
            "Executar quadro eléctrico novo com diferenciais e corte geral, cablagem "
            "conforme RTIEBT, pontos de luz, tomadas e circuitos dedicados para "
            "electrodomésticos. Prever infra-estrutura para carregamento de veículo "
            "eléctrico se aplicável. Certificação obrigatória por técnico responsável "
            "antes de fechar as paredes."
        ),
        "sort_order": 3,
        "budget_pct": 12.0,
        "depends_on": "Demolição e remoção",
    },
    {
        "name": "Canalização e águas",
        "category": "instalacoes",
        "description": (
            "Substituir toda a rede de abastecimento de água (tubagem multicamada ou "
            "PPR) e rede de drenagem de águas residuais (PP ou PVC). Verificar pressão "
            "de rede, instalar válvulas de corte por divisão e garantir declives mínimos "
            "regulamentares nos esgotos. Testar estanquidade antes de tapar."
        ),
        "sort_order": 4,
        "budget_pct": 10.0,
        "depends_on": "Demolição e remoção",
    },
    {
        "name": "AVAC",
        "category": "instalacoes",
        "description": (
            "Instalar sistema de climatização (unidades de ar condicionado split ou VRF "
            "conforme tipologia), ventilação mecânica controlada nas instalações "
            "sanitárias e cozinha, e recuperação de calor se previsto em projecto. "
            "Garantir caudais mínimos de renovação de ar segundo o RECS e localização "
            "discreta das unidades exteriores."
        ),
        "sort_order": 5,
        "budget_pct": 5.0,
        "depends_on": "Demolição e remoção",
    },
    {
        "name": "Cobertura e impermeabilização",
        "category": "exterior",
        "description": (
            "Reparar ou substituir cobertura (telha, terraço ou mansarda), aplicar "
            "sistema de impermeabilização em terraços e zonas húmidas exteriores, e "
            "tratar caleiras, algerozes e rufos. Verificar ausência de infiltrações "
            "após trabalhos e antes de iniciar acabamentos interiores."
        ),
        "sort_order": 6,
        "budget_pct": 8.0,
    },
    {
        "name": "Caixilharia e janelas",
        "category": "exterior",
        "description": (
            "Substituir caixilharia por perfis de alumínio com corte térmico ou madeira "
            "certificada, vidro duplo com factor solar adequado à orientação. Incluir "
            "oscilo-batente ou equivalente para ventilação, e garantir certificação "
            "energética de acordo com o REH. Verificar isolamento acústico mínimo "
            "exigido pelo RRAE."
        ),
        "sort_order": 7,
        "budget_pct": 8.0,
    },
    {
        "name": "Isolamento e gesso",
        "category": "interior",
        "description": (
            "Aplicar isolamento térmico e acústico nas paredes exteriores (ETICS ou "
            "contra-fachada) e tecto (lã de rocha ou XPS conforme solução), executar "
            "tecto falso em gesso cartonado com passagem de infra-estruturas, e "
            "efectuar regularização de paredes com estuque projectado ou gesso manual. "
            "Deixar superfícies prontas a pintar."
        ),
        "sort_order": 8,
        "budget_pct": 7.0,
        "depends_on": "Instalação eléctrica",
    },
    {
        "name": "Revestimentos: pavimentos e paredes",
        "category": "interior",
        "description": (
            "Assentar pavimento em toda a habitação (soalho de madeira, porcelanato ou "
            "vinílico de alta resistência), colocar rodapés e remates, e aplicar "
            "revestimento cerâmico ou pedra natural nas paredes de zonas húmidas "
            "(cozinha e instalações sanitárias). Garantir planeza e caimento correcto "
            "nos pavimentos das casas de banho."
        ),
        "sort_order": 9,
        "budget_pct": 10.0,
        "depends_on": "Isolamento e gesso",
    },
    {
        "name": "Cozinha",
        "category": "acabamentos",
        "description": (
            "Instalar móveis de cozinha (base e aéreos) com plano de trabalho em pedra "
            "natural ou compacto, incluindo electrodomésticos integrados (forno, "
            "placa, micro-ondas, exaustor e frigorífico). Ligar a canalização e "
            "electricidade, testar todos os equipamentos e verificar estanquidade "
            "das ligações."
        ),
        "sort_order": 10,
        "budget_pct": 10.0,
        "depends_on": "Revestimentos: pavimentos e paredes",
    },
    {
        "name": "Casas de banho",
        "category": "acabamentos",
        "description": (
            "Montar sanitários (sanita suspensa, lavatório e base de duche ou banheira), "
            "instalar torneiras monocomando, espelhos com iluminação LED integrada e "
            "acessórios de casa de banho (toalheiros, papeleiros). Verificar "
            "funcionamento de válvulas de descarga, ausência de fugas e ventilação "
            "adequada."
        ),
        "sort_order": 11,
        "budget_pct": 8.0,
        "depends_on": "Revestimentos: pavimentos e paredes",
    },
    {
        "name": "Pintura",
        "category": "acabamentos",
        "description": (
            "Aplicar primário e duas demãos de tinta plástica lavável em todas as "
            "paredes e tectos interiores, pintura de esmalte em rodapés, alizares e "
            "portas. Utilizar cores neutras e contemporâneas que maximizem a percepção "
            "de espaço e luminosidade. Retocar eventuais imperfeições antes da limpeza "
            "final."
        ),
        "sort_order": 12,
        "budget_pct": 5.0,
        "depends_on": "Revestimentos: pavimentos e paredes",
    },
    {
        "name": "Limpeza final",
        "category": "final",
        "description": (
            "Efectuar limpeza profissional pós-obra em todas as divisões: remoção de "
            "resíduos de construção, limpeza de vidros, sanitários, pavimentos e "
            "superfícies. Contratar empresa especializada em limpezas pós-obra para "
            "garantir padrão de entrega de imóvel pronto a habitar ou fotografar."
        ),
        "sort_order": 13,
        "budget_pct": 1.0,
        "depends_on": "Pintura",
    },
    {
        "name": "Punch list e verificação",
        "category": "final",
        "description": (
            "Percorrer o imóvel sistematicamente com a lista de verificação final: "
            "testar todos os interruptores, tomadas, torneiras, electrodomésticos, "
            "fechaduras e portadas. Registar e corrigir todas as não-conformidades "
            "antes da vistoria com o comprador ou arrendatário. Este marco não tem "
            "custo directo associado — está incluído na gestão de obra."
        ),
        "sort_order": 14,
        "budget_pct": 0.0,
        "depends_on": "Limpeza final",
    },
    {
        "name": "Fotografia profissional",
        "category": "final",
        "description": (
            "Contratar fotógrafo especializado em imobiliário para sessão fotográfica "
            "completa do imóvel: fotografias de grande angular de todas as divisões, "
            "exteriores, detalhes de acabamentos e, se aplicável, fotografias aéreas "
            "por drone. Incluir visita virtual 360° para aumentar o alcance dos "
            "anúncios online."
        ),
        "sort_order": 15,
        "budget_pct": 1.0,
    },
]


BUILDING_MILESTONES: list[dict] = FLIP_STANDARD_MILESTONES + [
    {
        "name": "Áreas comuns — escadaria e entrada",
        "category": "estrutura",
        "description": (
            "Reabilitar hall de entrada, escadaria e patamares comuns: substituição de "
            "pavimento (mármore, microcimento ou porcelanato), pintura de paredes e "
            "tectos, instalação de iluminação com sensor de presença e caixa de "
            "correio conforme regulamento condominial. Garantir conformidade com "
            "requisitos de acessibilidade do DL 163/2006."
        ),
        "sort_order": 16,
        "budget_pct": 5.0,
    },
    {
        "name": "Fachada",
        "category": "exterior",
        "description": (
            "Executar reabilitação de fachada: picagem de rebocos degradados, aplicação "
            "de sistema ETICS com isolamento (EPS ou MW conforme projecto), acabamento "
            "final em reboco texturado ou tinta de silicone. Incluir tratamento de "
            "varandas, cornijas e elementos decorativos de cantaria. Obter "
            "aprovação camarária sempre que exigido pelo RJUE."
        ),
        "sort_order": 17,
        "budget_pct": 8.0,
    },
]


AL_MILESTONES: list[dict] = FLIP_STANDARD_MILESTONES + [
    {
        "name": "Mobiliário e decoração",
        "category": "acabamentos",
        "description": (
            "Mobilar completamente o imóvel para alojamento local: camas com estrado e "
            "colchão de qualidade hoteleira, sofá, mesa de jantar e cadeiras, móveis "
            "de arrumação em todos os quartos e zona de estar. Aplicar decoração "
            "coerente com a identidade visual do alojamento (quadros, almofadas, "
            "plantas). Incluir roupa de cama, toalhas e kit de boas-vindas para "
            "abertura do alojamento."
        ),
        "sort_order": 16,
        "budget_pct": 12.0,
    },
    {
        "name": "Equipamento AL",
        "category": "acabamentos",
        "description": (
            "Instalar e configurar todos os equipamentos obrigatórios e diferenciais "
            "para alojamento local: televisão smart em cada quarto e zona comum, "
            "sistema de fechadura com código ou smart lock, wi-fi de alta velocidade "
            "com router em local estratégico, cofre de parede, secador de cabelo, "
            "ferro e tábua de engomar, e kit básico de cozinha (louça, talheres, "
            "copos, cafeteira). Registar o AL no Balcão Único Electrónico antes da "
            "primeira reserva."
        ),
        "sort_order": 17,
        "budget_pct": 5.0,
    },
]


def get_milestone_template(property_type: str, strategy: str) -> list[dict]:
    """Devolve a lista de marcos de obra adequada ao tipo de imóvel e estratégia.

    Args:
        property_type: Tipo de imóvel (ex: ``"apartamento"``, ``"moradia"``,
            ``"predio"``).
        strategy: Estratégia de investimento (ex: ``"flip"``, ``"arrendamento"``,
            ``"alojamento_local"``).

    Returns:
        Lista de dicts com os marcos de obra pré-configurados. Cada dict contém
        pelo menos ``name``, ``category``, ``description``, ``sort_order`` e
        ``budget_pct``, e opcionalmente ``depends_on``.
    """
    if strategy == "alojamento_local":
        return AL_MILESTONES

    if property_type == "predio":
        return BUILDING_MILESTONES

    return FLIP_STANDARD_MILESTONES
