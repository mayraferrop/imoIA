"use client";

import { useState, useEffect } from "react";
import { formatEUR, formatPercent, GRADE_COLORS } from "@/lib/utils";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "https://jurzdyncaxkgvcatyfdu.supabase.co";
const SUPABASE_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp1cnpkeW5jYXhrZ3ZjYXR5ZmR1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNzM2MDcsImV4cCI6MjA4OTk0OTYwN30.2DCCWcrhdwBLMxJ9hUbYkhOBQIgE_aD2jGNaZlAhO5k";
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://imoia.onrender.com";

interface CashFlowEntry {
  label: string;
  categoria: string;
  fluxo: number;
  acumulado: number;
  aquisicao?: number;
  obra?: number;
  pmt?: number;
  manut?: number;
  juros?: number;
  amort?: number;
  payoff?: number;
  saldo_devedor?: number;
}

interface SimulationResult {
  go_nogo: string;
  roi_pct: number;
  roi_simple_pct: number;
  net_profit: number;
  moic: number;
  total_investment: number;
  total_acquisition_cost: number;
  imt: number;
  imposto_selo: number;
  notario_registo: number;
  comissao_compra?: number;
  // 2a escritura (PF→JP)
  imt_2?: number;
  imt_2_original?: number;
  is_2?: number;
  escritura_2?: number;
  total_acquisition_cost_2?: number;
  entity_structure?: string;
  imt_resale_regime?: string;
  loan_amount?: number;
  monthly_payment?: number;
  payoff_at_sale?: number;
  bank_fees?: number;
  holding_months?: number;
  comissao_venda?: number;
  caixa_closing?: number;
  capital_gains_tax?: number;
  irc_estimated?: number;
  derrama_estimated?: number;
  total_corporate_tax?: number;
  irc_taxable_income?: number;
  capital_gains_detail?: Record<string, any>;
  roi_annualized_pct?: number;
  tir_anual_pct?: number;
  cash_on_cash_return_pct?: number;
  renovation_total?: number;
  holding_detail?: { meses: number; condominio_mensal: number; seguro_mensal: number; imi_mensal: number; total_mensal: number };
  total_holding_cost?: number;
  warnings?: string[];
  cash_flow?: { flows: CashFlowEntry[]; pico_caixa_necessario: number; saldo_final: number };
  model_id?: string;
}

interface ScenarioData {
  label: string;
  roi_pct: number;
  net_profit: number;
  mao: number;
}

interface IMTResult {
  imt?: number;
  imposto_selo?: number;
  total_impostos?: number;
  tabela?: string;
  nota?: string;
  itbi?: number;
  itbi_pct?: number;
}

interface MAOResult {
  mao_70pct?: number;
  mao_65pct?: number;
  mao_60pct?: number;
  nota?: string;
}

type Tab = "simulator" | "imt" | "mao" | "saved";

const CAT_COLORS: Record<string, string> = {
  aquisicao: "#2563EB",
  obra: "#D97706",
  holding: "#94A3B8",
  venda: "#16A34A",
};

export default function FinancialPage() {
  const [activeTab, setActiveTab] = useState<Tab>("simulator");
  // biome-ignore lint: auto-fetch
  const handleTabChange = (tab: Tab) => { setActiveTab(tab); if (tab === "saved") fetchSavedScenarios(); };
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [financingMode, setFinancingMode] = useState<"cash" | "mortgage">("cash");
  const [saveLoading, setSaveLoading] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const [modelId, setModelId] = useState<string | null>(null);
  const [scenarios, setScenarios] = useState<ScenarioData[] | null>(null);
  const [lastPayload, setLastPayload] = useState<Record<string, any> | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  // Modal de save com condicoes de pagamento
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [existingProperties, setExistingProperties] = useState<any[]>([]);
  const [selectedPropertyId, setSelectedPropertyId] = useState<string>("");
  const [scenarioName, setScenarioName] = useState("base");
  const [cpcvDate, setCpcvDate] = useState("");
  const [escrituraDate, setEscrituraDate] = useState("");
  const [tranches, setTranches] = useState<{ descricao: string; tipo: string; pct: number; dias_apos_cpcv: number }[]>([
    { descricao: "Sinal CPCV", tipo: "cpcv_sinal", pct: 5, dias_apos_cpcv: 0 },
    { descricao: "2a tranche", tipo: "tranche_intermedia", pct: 5, dias_apos_cpcv: 30 },
  ]);
  const [savedProjection, setSavedProjection] = useState<any>(null);
  const [savedScenarios, setSavedScenarios] = useState<any[]>([]);
  const [selectedScenario, setSelectedScenario] = useState<any>(null);
  const [scenariosLoading, setScenariosLoading] = useState(false);

  // IMT
  const [imtResult, setImtResult] = useState<IMTResult | null>(null);
  const [imtLoading, setImtLoading] = useState(false);

  // MAO
  const [maoResult, setMaoResult] = useState<MAOResult | null>(null);
  const [maoLoading, setMaoLoading] = useState(false);

  // Criar imóvel rápido (dentro do modal de salvar cenário)
  const [showNewProperty, setShowNewProperty] = useState(false);
  const [newPropLoading, setNewPropLoading] = useState(false);

  // CashFlow Pro export
  const [cfpProjects, setCfpProjects] = useState<{id: string; name: string}[]>([]);
  const [cfpProjectId, setCfpProjectId] = useState<string>("");
  const [cfpExporting, setCfpExporting] = useState(false);
  const [showCfpModal, setShowCfpModal] = useState(false);

  function loadCfpProjects() {
    fetch(`${API_BASE}/api/v1/financial/cashflow-pro/projects`)
      .then(r => r.ok ? r.json() : [])
      .then(setCfpProjects)
      .catch(() => {});
  }

  async function fetchSavedScenarios() {
    setScenariosLoading(true);
    try {
      const res = await fetch(
        `${SUPABASE_URL}/rest/v1/financial_models?select=id,property_id,scenario_name,go_nogo,roi_pct,net_profit,tir_anual_pct,purchase_price,estimated_sale_price,total_investment,created_at,properties(municipality,parish,property_type)&order=created_at.desc&limit=20`,
        { headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` } }
      );
      if (res.ok) setSavedScenarios(await res.json());
    } catch { /* ignore */ }
    finally { setScenariosLoading(false); }
  }

  async function loadScenarioDetail(modelId: string) {
    try {
      const res = await fetch(`${API_BASE}/api/v1/financial/${modelId}/projections`);
      if (res.ok) {
        const data = await res.json();
        setSelectedScenario(data);
      }
    } catch { /* ignore */ }
  }

  async function handleDeleteScenario(scenarioId: string) {
    if (!confirm("Excluir este cenário? Esta acção não pode ser desfeita.")) return;
    try {
      const res = await fetch(`${API_BASE}/api/v1/financial/${scenarioId}`, { method: "DELETE" });
      if (res.ok) {
        setSavedScenarios((prev) => prev.filter((s: any) => s.id !== scenarioId));
        if (selectedScenario?.model_id === scenarioId) setSelectedScenario(null);
      }
    } catch { /* ignore */ }
  }

  async function handleSimulate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setResult(null);
    setModelId(null);
    setScenarios(null);
    setSaveMsg("");
    setErrorMsg("");
    const fd = new FormData(e.currentTarget);

    // Helper: parse number from form, return fallback if empty/0
    const num = (name: string, fallback: number) => {
      const raw = fd.get(name);
      if (!raw || raw === "") return fallback;
      const v = Number(raw);
      return isNaN(v) || v === 0 ? fallback : v;
    };
    const numOrZero = (name: string) => {
      const raw = fd.get(name);
      if (!raw || raw === "") return 0;
      const v = Number(raw);
      return isNaN(v) ? 0 : v;
    };

    const purchasePrice = num("purchase_price", 295000);
    const estimatedSalePrice = num("estimated_sale_price", 500000);

    if (purchasePrice <= 0) {
      setErrorMsg("Preço de compra é obrigatório.");
      setLoading(false);
      return;
    }
    if (estimatedSalePrice <= 0) {
      setErrorMsg("Preço de venda (ARV) é obrigatório.");
      setLoading(false);
      return;
    }

    const payload: Record<string, any> = {
      purchase_price: purchasePrice,
      renovation_budget: numOrZero("renovation_cost"),
      estimated_sale_price: estimatedSalePrice,
      additional_holding_months: num("holding_months", 6),
      municipality: (fd.get("municipality") as string) || "Lisboa",
      property_type: fd.get("property_type") as string || "secondary",
      country: fd.get("country") as string || "PT",
      entity_structure: fd.get("entity_structure") as string || "pf_jp",
      imt_resale_regime: fd.get("imt_resale_regime") as string || "none",
      financing_type: financingMode,
      renovation_duration_months: num("renovation_duration_months", 3),
      comissao_venda_pct: num("comissao_venda_pct", 6.15),
      comissao_compra_pct: numOrZero("comissao_compra_pct"),
      renovation_contingency_pct: numOrZero("renovation_contingency_pct"),
      monthly_condominio: num("monthly_condominio", 50),
      annual_insurance: num("annual_insurance", 300),
      monthly_consumos: num("monthly_consumos", 80),
      roi_target_pct: num("roi_target_pct", 15),
      scenario_name: "simulacao",
    };

    if (financingMode === "mortgage") {
      payload.loan_pct_purchase = num("loan_pct_purchase", 75);
      payload.loan_pct_renovation = numOrZero("loan_pct_renovation");
      payload.interest_rate_pct = num("interest_rate_pct", 2.73);
      payload.loan_term_months = num("loan_term_years", 30) * 12;
    }

    setLastPayload(payload);

    try {
      const res = await fetch(`${API_BASE}/api/v1/financial/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const data = await res.json();
        setResult(data);
        if (data.model_id) setModelId(data.model_id);
      } else {
        const err = await res.json().catch(() => null);
        const detail = err?.detail;
        if (Array.isArray(detail)) {
          setErrorMsg(detail.map((d: any) => `${d.loc?.join(".")}: ${d.msg}`).join("; "));
        } else {
          setErrorMsg(`Erro ${res.status}: ${typeof detail === "string" ? detail : "Falha na simulação"}`);
        }
      }
    } catch (err) {
      setErrorMsg("Erro de comunicação com a API. Verifique a ligação.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveScenario() {
    if (!lastPayload) return;
    if (!selectedPropertyId) {
      setSaveMsg("Seleccione um imóvel para vincular o cenário.");
      return;
    }
    if (!cpcvDate || !escrituraDate) {
      setSaveMsg("Preencha as datas do CPCV e escritura.");
      return;
    }
    setSaveLoading(true);
    setSaveMsg("");

    // Calcular tranche da escritura (restante ate 100%)
    const somaPct = tranches.reduce((sum, t) => sum + t.pct, 0);
    const escrituraPct = Math.max(100 - somaPct, 0);
    const purchasePrice = lastPayload.purchase_price || 295000;

    // Calcular data real de cada tranche: CPCV + dias_apos_cpcv
    const cpcvMs = new Date(cpcvDate).getTime();
    const allTranches = [
      ...tranches.map((t) => {
        const trancheDate = new Date(cpcvMs + t.dias_apos_cpcv * 86400000);
        return {
          ...t,
          valor: Math.round(purchasePrice * t.pct / 100),
          data: trancheDate.toISOString().slice(0, 10),
        };
      }),
      {
        descricao: "Escritura",
        tipo: "escritura",
        pct: escrituraPct,
        valor: Math.round(purchasePrice * escrituraPct / 100),
        data: escrituraDate,
        dias_apos_cpcv: 0,
      },
    ];

    const body = {
      ...lastPayload,
      property_id: selectedPropertyId || null,
      scenario_name: scenarioName,
      cpcv_date: cpcvDate,
      escritura_date: escrituraDate,
      tranches: allTranches,
    };

    try {
      const res = await fetch(`${API_BASE}/api/v1/financial/save-scenario`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const saved = await res.json();
        setModelId(saved.model_id);
        setSaveMsg(`Cenário "${scenarioName}" salvo com ${saved.projections_count} períodos de projeção!`);
        setShowSaveModal(false);
        // Buscar projeção para mostrar
        setSavedProjection({
          model_id: saved.model_id,
          cpcv_date: cpcvDate,
          escritura_date: escrituraDate,
          tranches: allTranches,
          cash_flow: saved.cash_flow,
          tir_anual_pct: saved.tir_anual_pct,
          go_nogo: saved.go_nogo,
          net_profit: saved.net_profit,
          total_investment: saved.total_investment,
        });
      } else {
        const err = await res.json().catch(() => null);
        setSaveMsg(`Erro: ${err?.detail || "Falha ao salvar cenário"}`);
      }
    } catch {
      setSaveMsg("Erro de comunicação com a API.");
    } finally {
      setSaveLoading(false);
    }
  }

  async function fetchScenarios(mId: string) {
    try {
      const res = await fetch(`${API_BASE}/api/v1/financial/scenarios/${mId}`);
      if (res.ok) {
        const data = await res.json();
        if (data.scenarios) setScenarios(data.scenarios);
      }
    } catch {
      // ignore
    }
  }

  async function handleIMT(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setImtLoading(true);
    setImtResult(null);
    const fd = new FormData(e.currentTarget);
    const body = {
      value: Number(fd.get("imt_value")) || 295000,
      country: fd.get("imt_country") as string || "PT",
      is_hpp: fd.get("imt_hpp") === "on",
    };
    try {
      const res = await fetch(`${API_BASE}/api/v1/financial/quick-imt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) setImtResult(await res.json());
    } catch {
      // ignore
    } finally {
      setImtLoading(false);
    }
  }

  async function handleMAO(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setMaoLoading(true);
    setMaoResult(null);
    const fd = new FormData(e.currentTarget);
    const body = {
      arv: Number(fd.get("mao_arv")) || 500000,
      renovation_total: Number(fd.get("mao_reno")) || 100000,
    };
    try {
      const res = await fetch(`${API_BASE}/api/v1/financial/mao`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) setMaoResult(await res.json());
    } catch {
      // ignore
    } finally {
      setMaoLoading(false);
    }
  }

  const goNoGoColor = result?.go_nogo === "go" ? "#16A34A" : result?.go_nogo === "marginal" ? "#D97706" : "#DC2626";
  const goNoGoLabel = result?.go_nogo === "go" ? "GO" : result?.go_nogo === "marginal" ? "MARGINAL" : "NO GO";
  const cashFlow = result?.cash_flow;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">M3 — Simulador Financeiro</h1>
        <p className="text-sm text-slate-500 mt-1">Simular investimento fix and flip</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-100 rounded-lg p-1 w-fit">
        {([
          ["simulator", "Simulador"],
          ["imt", "Calculadora IMT"],
          ["mao", "Calculadora MAO"],
          ["saved", "Cenários Salvos"],
        ] as [Tab, string][]).map(([key, label]) => (
          <button
            key={key}
            onClick={() => handleTabChange(key)}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === key ? "bg-white text-teal-700 shadow-sm" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ===== IMT Calculator ===== */}
      {activeTab === "imt" && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 max-w-2xl">
          <h2 className="text-lg font-semibold mb-4">Cálculo rápido de IMT</h2>
          <form onSubmit={handleIMT} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Field name="imt_value" label="Valor do imóvel (€)" placeholder="295000" />
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">País</label>
                <select name="imt_country" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-teal-500">
                  <option value="PT">Portugal</option>
                  <option value="BR">Brasil</option>
                </select>
              </div>
              <div className="flex items-end pb-2">
                <label className="flex items-center gap-2 text-sm text-slate-700">
                  <input type="checkbox" name="imt_hpp" className="rounded border-slate-300 text-teal-600 focus:ring-teal-500" />
                  HPP (habitação própria)
                </label>
              </div>
            </div>
            <button
              type="submit"
              disabled={imtLoading}
              className="px-6 py-2.5 bg-teal-700 text-white rounded-lg text-sm font-medium hover:bg-teal-800 disabled:opacity-50 transition-colors"
            >
              {imtLoading ? "A calcular..." : "Calcular IMT"}
            </button>
          </form>
          {imtResult && (
            <div className="mt-6 grid grid-cols-3 gap-4">
              {imtResult.imt != null && <KpiCard label="IMT" value={formatEUR(imtResult.imt)} />}
              {imtResult.imposto_selo != null && <KpiCard label="Imposto de Selo" value={formatEUR(imtResult.imposto_selo)} />}
              {imtResult.total_impostos != null && <KpiCard label="Total Impostos" value={formatEUR(imtResult.total_impostos)} />}
              {imtResult.itbi != null && <KpiCard label="ITBI" value={formatEUR(imtResult.itbi)} />}
              {imtResult.itbi_pct != null && <KpiCard label="ITBI %" value={`${imtResult.itbi_pct}%`} />}
              {imtResult.nota && (
                <p className="col-span-3 text-xs text-slate-500">
                  {imtResult.tabela && `Tabela: ${imtResult.tabela} | `}{imtResult.nota}
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* ===== MAO Calculator ===== */}
      {activeTab === "mao" && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 max-w-2xl">
          <h2 className="text-lg font-semibold mb-2">MAO — Maximum Allowable Offer (Regra 70%)</h2>
          <p className="text-xs text-slate-500 mb-4">MAO = ARV x Factor - Custo Obra</p>
          <form onSubmit={handleMAO} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Field name="mao_arv" label="ARV — Valor pós-obra (€)" placeholder="500000" />
              <Field name="mao_reno" label="Custo total de obra (€)" placeholder="100000" />
            </div>
            <button
              type="submit"
              disabled={maoLoading}
              className="px-6 py-2.5 bg-teal-700 text-white rounded-lg text-sm font-medium hover:bg-teal-800 disabled:opacity-50 transition-colors"
            >
              {maoLoading ? "A calcular..." : "Calcular MAO"}
            </button>
          </form>
          {maoResult && (
            <div className="mt-6 grid grid-cols-3 gap-4">
              <KpiCard label="MAO 70% (activo)" value={formatEUR(maoResult.mao_70pct)} color="#16A34A" />
              <KpiCard label="MAO 65% (normal)" value={formatEUR(maoResult.mao_65pct)} color="#D97706" />
              <KpiCard label="MAO 60% (lento)" value={formatEUR(maoResult.mao_60pct)} color="#DC2626" />
              {maoResult.nota && <p className="col-span-3 text-xs text-slate-500">{maoResult.nota}</p>}
            </div>
          )}
        </div>
      )}

      {/* ===== Full Simulator ===== */}
      {activeTab === "simulator" && (
        <>
          <div className="simulator-layout">
            {/* Form */}
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <h2 className="text-lg font-semibold mb-4">Parâmetros</h2>
              <form onSubmit={handleSimulate} className="space-y-5">
                {/* Compra */}
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Compra</p>
                  <div className="grid grid-cols-2 gap-3">
                    <Field name="purchase_price" label="Preço compra (€)" placeholder="295000" />
                    <Field name="municipality" label="Concelho" placeholder="Lisboa" type="text" />
                  </div>
                </div>

                {/* Obra */}
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Obra</p>
                  <div className="grid grid-cols-3 gap-3">
                    <Field name="renovation_cost" label="Orçamento (€)" placeholder="98400" />
                    <Field name="renovation_duration_months" label="Duração (meses)" placeholder="3" />
                    <Field name="renovation_contingency_pct" label="Contingência %" placeholder="0" />
                  </div>
                </div>

                {/* Estrutura e IMT */}
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Estrutura da Operação</p>
                  <div className="grid grid-cols-3 gap-3">
                    <div className="form-field">
                      <label className="block text-sm font-medium text-slate-700 mb-1">Entidade</label>
                      <select name="entity_structure" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-teal-500">
                        <option value="pf_jp">PF → JP</option>
                        <option value="pf_only">PF only</option>
                        <option value="jp_only">JP only</option>
                      </select>
                    </div>
                    <div className="form-field">
                      <label className="block text-sm font-medium text-slate-700 mb-1">Regime IMT</label>
                      <select name="imt_resale_regime" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-teal-500">
                        <option value="none">Sem benefício</option>
                        <option value="reembolso">Reembolso</option>
                        <option value="isencao">Isenção</option>
                      </select>
                    </div>
                    <Field name="comissao_compra_pct" label="Com. compra %" placeholder="0" />
                  </div>
                </div>

                {/* Financiamento */}
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Financiamento</p>
                  {/* Toggle Cash / Financiado */}
                  <div className="flex gap-1 bg-slate-100 rounded-lg p-1 mb-3">
                    <button
                      type="button"
                      onClick={() => setFinancingMode("cash")}
                      className={`flex-1 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                        financingMode === "cash" ? "bg-white text-teal-700 shadow-sm" : "text-slate-500 hover:text-slate-700"
                      }`}
                    >
                      Cash
                    </button>
                    <button
                      type="button"
                      onClick={() => setFinancingMode("mortgage")}
                      className={`flex-1 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                        financingMode === "mortgage" ? "bg-white text-teal-700 shadow-sm" : "text-slate-500 hover:text-slate-700"
                      }`}
                    >
                      Financiado
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="form-field relative group">
                      <label className={`block text-sm font-medium mb-1 ${financingMode === "cash" ? "text-slate-400" : "text-slate-700"}`}>% financiado compra</label>
                      <input
                        name="loan_pct_purchase"
                        type="number"
                        placeholder="75"
                        step="any"
                        disabled={financingMode === "cash"}
                        className={`w-full border rounded-lg px-3 py-2 text-sm outline-none ${
                          financingMode === "cash"
                            ? "bg-slate-100 border-slate-200 text-slate-400 cursor-not-allowed"
                            : "border-slate-300 focus:ring-2 focus:ring-teal-500"
                        }`}
                      />
                      {financingMode === "cash" && (
                        <div className="hidden group-hover:block absolute z-10 bottom-full left-0 mb-1 bg-white border border-slate-200 rounded-lg shadow-lg p-2 text-xs text-slate-500 w-48">
                          Disponível no modo Financiado
                        </div>
                      )}
                    </div>
                    <div className="form-field relative group">
                      <label className={`block text-sm font-medium mb-1 ${financingMode === "cash" ? "text-slate-400" : "text-slate-700"}`}>% financiado obra</label>
                      <input
                        name="loan_pct_renovation"
                        type="number"
                        placeholder="0"
                        step="any"
                        disabled={financingMode === "cash"}
                        className={`w-full border rounded-lg px-3 py-2 text-sm outline-none ${
                          financingMode === "cash"
                            ? "bg-slate-100 border-slate-200 text-slate-400 cursor-not-allowed"
                            : "border-slate-300 focus:ring-2 focus:ring-teal-500"
                        }`}
                      />
                      {financingMode === "cash" && (
                        <div className="hidden group-hover:block absolute z-10 bottom-full left-0 mb-1 bg-white border border-slate-200 rounded-lg shadow-lg p-2 text-xs text-slate-500 w-48">
                          Disponível no modo Financiado
                        </div>
                      )}
                    </div>
                    <div className="form-field relative group">
                      <label className={`block text-sm font-medium mb-1 ${financingMode === "cash" ? "text-slate-400" : "text-slate-700"}`}>TAN % (a.a.)</label>
                      <input
                        name="interest_rate_pct"
                        type="number"
                        placeholder="2.73"
                        step="any"
                        disabled={financingMode === "cash"}
                        className={`w-full border rounded-lg px-3 py-2 text-sm outline-none ${
                          financingMode === "cash"
                            ? "bg-slate-100 border-slate-200 text-slate-400 cursor-not-allowed"
                            : "border-slate-300 focus:ring-2 focus:ring-teal-500"
                        }`}
                      />
                    </div>
                    <div className="form-field relative group">
                      <label className={`block text-sm font-medium mb-1 ${financingMode === "cash" ? "text-slate-400" : "text-slate-700"}`}>Prazo (anos)</label>
                      <input
                        name="loan_term_years"
                        type="number"
                        placeholder="30"
                        step="any"
                        disabled={financingMode === "cash"}
                        className={`w-full border rounded-lg px-3 py-2 text-sm outline-none ${
                          financingMode === "cash"
                            ? "bg-slate-100 border-slate-200 text-slate-400 cursor-not-allowed"
                            : "border-slate-300 focus:ring-2 focus:ring-teal-500"
                        }`}
                      />
                    </div>
                  </div>
                </div>

                {/* Venda */}
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Venda</p>
                  <div className="grid grid-cols-2 gap-3">
                    <Field name="estimated_sale_price" label="Preço venda / ARV (€)" placeholder="500000" />
                    <Field name="holding_months" label="Meses até venda" placeholder="6" />
                  </div>
                  <div className="grid grid-cols-4 gap-3 mt-3">
                    <Field name="comissao_venda_pct" label="Com. venda %" placeholder="6.15" />
                    <Field name="monthly_condominio" label="Condomínio (€)" placeholder="50" />
                    <Field name="annual_insurance" label="Seguro anual (€)" placeholder="300" />
                    <Field name="monthly_consumos" label="Consumos (€/mês)" placeholder="80" />
                  </div>
                </div>

                {/* Outros */}
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Outros</p>
                  <div className="grid grid-cols-3 gap-3">
                    <div className="form-field">
                      <label className="block text-sm font-medium text-slate-700 mb-1">Tipo imóvel</label>
                      <select name="property_type" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-teal-500">
                        <option value="secondary">Investimento</option>
                        <option value="primary">HPP</option>
                      </select>
                    </div>
                    <div className="form-field">
                      <label className="block text-sm font-medium text-slate-700 mb-1">País</label>
                      <select name="country" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-teal-500">
                        <option value="PT">Portugal</option>
                        <option value="BR">Brasil</option>
                      </select>
                    </div>
                    <Field name="roi_target_pct" label="ROI target %" placeholder="15" />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-teal-700 text-white py-2.5 rounded-lg font-medium hover:bg-teal-800 disabled:opacity-50 transition-colors"
                >
                  {loading ? "A simular..." : "Simular"}
                </button>
              </form>
            </div>

            {/* Error message */}
            {errorMsg && (
              <div className="bg-red-50 border border-red-200 rounded-xl p-4">
                <p className="text-sm text-red-700">{errorMsg}</p>
              </div>
            )}

            {/* Result */}
            {result && (() => {
              const imtReembolso = result.imt_resale_regime === "reembolso" && result.entity_structure === "pf_jp"
                ? (result.imt_2 ?? 0) : 0;
              const totalTax = result.total_corporate_tax ?? result.capital_gains_tax ?? 0;
              const lucroPosImpostos = result.net_profit - totalTax;
              const holdingDetail = result.holding_detail;
              const totalEscritura1 = (result.imt ?? 0) + (result.imposto_selo ?? 0) + (result.notario_registo ?? 0) + (result.comissao_compra ?? 0);
              const roiTarget = lastPayload?.roi_target_pct ?? 15;

              // Custo total do projecto (independente de financiamento — mede o deal)
              const custoTotalProjecto = (lastPayload?.purchase_price ?? 0)
                + (result.renovation_total ?? 0)
                + totalEscritura1
                + (result.total_acquisition_cost_2 ?? 0)
                + (result.total_holding_cost ?? 0);

              // Juros + custos hipoteca pagos (efeito do financiamento)
              const jurosPagos = (result.monthly_payment ?? 0) * (result.holding_months ?? 0) - ((result.loan_amount ?? 0) - (result.payoff_at_sale ?? 0));
              const custosHipoteca = result.bank_fees ?? 0;

              // Margem bruta = qualidade do deal (nao muda com financiamento)
              const lucroSemJuros = result.net_profit + Math.max(jurosPagos, 0) + custosHipoteca;
              const margemBruta = custoTotalProjecto > 0
                ? (lucroSemJuros / custoTotalProjecto * 100) : 0;
              const lucroLiqSemJuros = lucroPosImpostos + Math.max(jurosPagos, 0) + custosHipoteca;
              const margemLiquida = custoTotalProjecto > 0
                ? (lucroLiqSemJuros / custoTotalProjecto * 100) : 0;

              // Caixa investido = o que saiu do bolso (total_investment - emprestimo)
              const caixaInvestido = result.total_investment - (result.loan_amount ?? 0);

              // ROI equity e ROI anualizado
              const roiEquity = caixaInvestido > 0 ? (result.net_profit / caixaInvestido) : 0;
              const holdingMonths = result.holding_months ?? 9;
              const roiAnualizado = roiEquity !== 0 && holdingMonths > 0
                ? (Math.pow(1 + roiEquity, 12 / holdingMonths) - 1) * 100
                : 0;

              return (
              <div className="space-y-6">
                {/* Go/No-Go badge + KPIs */}
                <div className="bg-white rounded-xl border border-slate-200 p-6">
                  <div className="flex items-center justify-between mb-6">
                    <h2 className="text-lg font-semibold">Resultado</h2>
                    <div className="relative group">
                      <span
                        className="px-6 py-2 rounded-xl text-lg font-bold text-white cursor-help"
                        style={{ backgroundColor: goNoGoColor }}
                      >
                        {goNoGoLabel}
                      </span>
                      <div className="hidden group-hover:block absolute z-10 top-full right-0 mt-2 w-72 bg-white border border-slate-200 rounded-lg shadow-lg p-3 text-xs text-slate-600 leading-relaxed">
                        <p className="font-bold mb-1">TIR anual {(result.tir_anual_pct ?? result.roi_pct ?? 0).toFixed(1)}% vs target {roiTarget}%</p>
                        <p>TIR &ge; {roiTarget}% &rarr; GO</p>
                        <p>TIR &ge; {(roiTarget * 0.7).toFixed(0)}% (70% target) &rarr; MARGINAL</p>
                        <p>TIR &lt; {(roiTarget * 0.7).toFixed(0)}% &rarr; NO GO</p>
                      </div>
                    </div>
                  </div>

                  <div className="metrics-grid">
                    <KpiCard
                      label="Margem bruta"
                      value={`${margemBruta.toFixed(1)}%`}
                      color={margemBruta >= 0 ? "#0F766E" : "#DC2626"}
                      tooltip={`Lucro sem juros / Custo total projecto = ${formatEUR(lucroSemJuros)} / ${formatEUR(custoTotalProjecto)}. Mede a qualidade do deal independente de quem financia.`}
                    />
                    <KpiCard
                      label="Margem líquida"
                      value={`${margemLiquida.toFixed(1)}%`}
                      color={margemLiquida >= 0 ? "#0F766E" : "#DC2626"}
                      tooltip={`Lucro líq. sem juros / Custo total projecto = ${formatEUR(lucroLiqSemJuros)} / ${formatEUR(custoTotalProjecto)}. Retorno real pós-impostos.`}
                    />
                    <KpiCard
                      label="TIR anual"
                      value={`${(result.tir_anual_pct ?? result.roi_pct ?? 0).toFixed(1)}%`}
                      tooltip={`Taxa Interna de Retorno anualizada. Pesa cada fluxo pelo mês exacto: CPCV, escritura, obra faseada, venda, reembolso IMT. Padrão da indústria.`}
                    />
                    <KpiCard
                      label="ROI anualizado"
                      value={`${roiAnualizado.toFixed(1)}%`}
                      tooltip={`(1 + ROI equity)^(12/${holdingMonths}m) - 1 = (1 + ${(roiEquity * 100).toFixed(1)}%)^${(12/holdingMonths).toFixed(1)} - 1. Converte o ROI equity para base anual para comparar deals com durações diferentes.`}
                    />
                  </div>

                  {/* Linha 2: lucro absoluto + ROI equity */}
                  <div className="metrics-grid mt-3 pt-3 border-t border-slate-100">
                    <KpiCard
                      label="Lucro bruto"
                      value={formatEUR(result.net_profit)}
                      color={result.net_profit >= 0 ? "#0F766E" : "#DC2626"}
                      tooltip="Retorno total (venda + reembolsos) menos capital investido."
                    />
                    {totalTax > 0 && (
                      <KpiCard
                        label="Lucro pós-impostos"
                        value={formatEUR(lucroPosImpostos)}
                        color={lucroPosImpostos >= 0 ? "#0F766E" : "#DC2626"}
                        tooltip={`Lucro ${formatEUR(result.net_profit)} - impostos ${formatEUR(totalTax)} = ${formatEUR(lucroPosImpostos)}`}
                      />
                    )}
                    <KpiCard
                      label="ROI equity"
                      value={caixaInvestido > 0 ? `${(result.net_profit / caixaInvestido * 100).toFixed(1)}%` : "N/A"}
                      tooltip={caixaInvestido > 0
                        ? `Lucro ${formatEUR(result.net_profit)} / Caixa investido ${formatEUR(caixaInvestido)} = ${(result.net_profit / caixaInvestido * 100).toFixed(1)}%. ${(result.loan_amount ?? 0) > 0 ? "Com financiamento sobe porque menos capital próprio é usado." : "Num deal cash, ROI equity = margem bruta."}`
                        : "Capital investido inválido. Verificar parâmetros."}
                    />
                    <KpiCard
                      label="Caixa investido"
                      value={formatEUR(caixaInvestido)}
                      tooltip={`Investimento total ${formatEUR(result.total_investment)} - Empréstimo ${formatEUR(result.loan_amount ?? 0)} = ${formatEUR(caixaInvestido)}. O dinheiro que saiu do teu bolso.`}
                      color={caixaInvestido > 0 ? undefined : "#DC2626"}
                    />
                  </div>

                  {/* Warnings */}
                  {result.warnings && result.warnings.length > 0 && (
                    <div className="mt-4 space-y-2">
                      {result.warnings.map((w, i) => (
                        <div key={i} className="bg-amber-50 text-amber-700 text-sm px-3 py-2 rounded-lg">{w}</div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Breakdown investimento */}
                <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
                  <h3 className="text-sm font-semibold text-teal-700">Investimento</h3>
                  {(result.loan_amount ?? 0) > 0 ? (() => {
                    const loanPctPurchase = lastPayload?.loan_pct_purchase ?? 0;
                    const loanPctReno = lastPayload?.loan_pct_renovation ?? 0;
                    const loanCompra = (lastPayload?.purchase_price ?? 0) * loanPctPurchase / 100;
                    const loanObra = (result.renovation_total ?? 0) * loanPctReno / 100;
                    const equityCompra = (lastPayload?.purchase_price ?? 0) - loanCompra;
                    const equityObra = (result.renovation_total ?? 0) - loanObra;
                    return (
                    <>
                      {/* Modo Financiado — custo total, subtrair emprestimo 1x no final */}
                      <DetailRow label="Preço de compra" value={formatEUR(lastPayload?.purchase_price)} />
                      {(result.renovation_total ?? 0) > 0 && (
                        <DetailRow label="Obra" value={formatEUR(result.renovation_total)} />
                      )}
                      <DetailRow label="Custos 1ª escritura" value={formatEUR(totalEscritura1)} />
                      {result.entity_structure === "pf_jp" && (result.total_acquisition_cost_2 ?? 0) > 0 && (
                        <DetailRow label="Custos 2ª escritura" value={formatEUR(result.total_acquisition_cost_2)} />
                      )}
                      <DetailRow label="Custos hipoteca" value={formatEUR(result.bank_fees)} />
                      {holdingDetail && (
                        <>
                          <DetailRow label={`Manutenção (${holdingDetail.meses}m × ${formatEUR(holdingDetail.total_mensal)}/m)`} value={formatEUR(result.total_holding_cost)} />
                          <p className="text-xs text-slate-400 -mt-1 ml-1">
                            Cond. {formatEUR(holdingDetail.condominio_mensal)} + Seguro {formatEUR(holdingDetail.seguro_mensal)} + IMI {formatEUR(holdingDetail.imi_mensal)} = {formatEUR(holdingDetail.total_mensal)}/m
                          </p>
                        </>
                      )}
                      <DetailRow label={`Prestações pagas (${result.holding_months}m × ${formatEUR(result.monthly_payment)}/m)`} value={formatEUR((result.monthly_payment ?? 0) * (result.holding_months ?? 0))} />
                      <div className="border-t border-slate-300 pt-2 space-y-1">
                        <DetailRow label="Custo total do projecto" value={formatEUR(result.total_investment)} bold />
                      </div>
                      {/* Decomposicao do financiamento */}
                      <div className="bg-blue-50 rounded-lg p-3 space-y-1">
                        <p className="text-xs font-semibold text-blue-700 uppercase mb-1">Financiamento</p>
                        <DetailRow label={`Empréstimo compra (${loanPctPurchase}%)`} value={formatEUR(loanCompra)} color="#2563EB" />
                        {loanObra > 0 && (
                          <DetailRow label={`Empréstimo obra (${loanPctReno}%)`} value={formatEUR(loanObra)} color="#2563EB" />
                        )}
                        <DetailRow label="Empréstimo total" value={formatEUR(result.loan_amount)} bold color="#2563EB" />
                      </div>
                      <div className="bg-teal-50 rounded-lg p-3 space-y-1">
                        <p className="text-xs font-semibold text-teal-700 uppercase mb-1">Capital próprio (do teu bolso)</p>
                        <DetailRow label="Equity compra" value={formatEUR(equityCompra)} />
                        <DetailRow label="Equity obra" value={formatEUR(equityObra)} />
                        <DetailRow label="Custos (escrituras + hipoteca + manut. + PMT)" value={formatEUR(caixaInvestido - equityCompra - equityObra)} />
                        <div className="border-t border-teal-200 pt-1">
                          <DetailRow label="Total caixa investido" value={formatEUR(caixaInvestido)} bold color="#0F766E" />
                        </div>
                      </div>
                    </>
                    );
                  })() : (
                    <>
                      {/* Modo Cash — breakdown simples */}
                      <DetailRow label="Preço de compra (equity)" value={formatEUR(lastPayload?.purchase_price)} />
                      <DetailRow label="Custos 1ª escritura" value={formatEUR(totalEscritura1)} />
                      {result.entity_structure === "pf_jp" && (result.total_acquisition_cost_2 ?? 0) > 0 && (
                        <DetailRow label="Custos 2ª escritura" value={formatEUR(result.total_acquisition_cost_2)} />
                      )}
                      {(result.renovation_total ?? 0) > 0 && (
                        <DetailRow label="Obra" value={formatEUR(result.renovation_total)} />
                      )}
                      {holdingDetail && (
                        <>
                          <DetailRow label={`Manutenção (${holdingDetail.meses}m × ${formatEUR(holdingDetail.total_mensal)}/m)`} value={formatEUR(result.total_holding_cost)} />
                          <p className="text-xs text-slate-400 -mt-1 ml-1">
                            Cond. {formatEUR(holdingDetail.condominio_mensal)} + Seguro {formatEUR(holdingDetail.seguro_mensal)} + IMI {formatEUR(holdingDetail.imi_mensal)} = {formatEUR(holdingDetail.total_mensal)}/m
                          </p>
                        </>
                      )}
                      <div className="border-t border-slate-300 pt-2">
                        <DetailRow label="Total investido (caixa desembolsado)" value={formatEUR(result.total_investment)} bold />
                      </div>
                    </>
                  )}
                </div>

                {/* 1ª Escritura */}
                <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-teal-700">
                      1ª Escritura {result.entity_structure === "pf_jp" ? "(Vendedor → PF)" : result.entity_structure === "jp_only" ? "(Vendedor → JP)" : "(Vendedor → PF)"}
                    </h3>
                    <span className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-600">
                      {result.entity_structure === "pf_jp" ? "PF → JP" : result.entity_structure === "jp_only" ? "JP only" : "PF only"}
                    </span>
                  </div>
                  <DetailRow label="IMT (tabela OE2026)" value={formatEUR(result.imt)} />
                  <DetailRow label="Imposto de Selo (0,8%)" value={formatEUR(result.imposto_selo)} />
                  <DetailRow label="Escritura + Registo" value={formatEUR(result.notario_registo)} />
                  {result.comissao_compra != null && result.comissao_compra > 0 && (
                    <DetailRow label="Comissão compra" value={formatEUR(result.comissao_compra)} />
                  )}
                  <div className="border-t border-slate-300 pt-2">
                    <DetailRow label="Total 1ª escritura" value={formatEUR(totalEscritura1)} bold />
                  </div>
                </div>

                {/* 2ª Escritura (PF→JP) */}
                {result.entity_structure === "pf_jp" && result.total_acquisition_cost_2 != null && (
                  <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-semibold text-purple-700">2ª Escritura (PF → JP)</h3>
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        result.imt_resale_regime === "isencao" ? "bg-green-100 text-green-700" :
                        result.imt_resale_regime === "reembolso" ? "bg-amber-100 text-amber-700" :
                        "bg-red-100 text-red-700"
                      }`}>
                        {result.imt_resale_regime === "isencao" ? "Isento IMT" :
                         result.imt_resale_regime === "reembolso" ? "IMT c/ reembolso" :
                         "Paga IMT 2x"}
                      </span>
                    </div>
                    <DetailRow
                      label={`IMT 2ª transmissão${result.imt_resale_regime === "isencao" ? " (isento)" : ""}`}
                      value={formatEUR(result.imt_2)}
                    />
                    <DetailRow label="Imposto de Selo 2ª" value={formatEUR(result.is_2)} />
                    <DetailRow label="Escritura 2ª" value={formatEUR(result.escritura_2)} />
                    <div className="border-t border-slate-300 pt-2">
                      <DetailRow label="Total 2ª escritura" value={formatEUR(result.total_acquisition_cost_2)} bold />
                    </div>
                    {result.imt_resale_regime === "reembolso" && (
                      <p className="text-xs text-amber-600">O IMT de {formatEUR(result.imt_2_original)} será reembolsado 12 meses após a 2ª escritura</p>
                    )}
                  </div>
                )}

                {result.loan_amount != null && result.loan_amount > 0 && (
                  <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
                    <h3 className="text-sm font-semibold text-teal-700">Financiamento</h3>
                    <DetailRow label="Empréstimo" value={formatEUR(result.loan_amount)} />
                    <DetailRow label="PMT mensal" value={formatEUR(result.monthly_payment)} />
                    <DetailRow label={`Payoff mês ${result.holding_months ?? 0}`} value={formatEUR(result.payoff_at_sale)} />
                    <DetailRow label="Custos hipoteca" value={formatEUR(result.bank_fees)} />
                    {result.cash_on_cash_return_pct != null && (
                      <DetailRow label="Cash-on-cash return" value={`${result.cash_on_cash_return_pct.toFixed(1)}%`} />
                    )}
                  </div>
                )}

                {/* Resultado cash (Melhoria 2 — reembolso visivel) */}
                <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
                  <h3 className="text-sm font-semibold text-teal-700">Resultado Cash</h3>
                  <DetailRow label="Caixa no closing (venda - payoff)" value={formatEUR(result.caixa_closing)} />
                  {imtReembolso > 0 && (
                    <DetailRow label="Reembolso IMT (12 meses depois)" value={`+${formatEUR(imtReembolso)}`} color="#16A34A" />
                  )}
                  <DetailRow label="Retorno total" value={formatEUR((result.caixa_closing ?? 0) + imtReembolso)} />
                  <DetailRow label="Capital investido" value={`-${formatEUR(result.total_investment)}`} />
                  <div className="border-t border-slate-300 pt-2">
                    <DetailRow
                      label="Lucro bruto (cash)"
                      value={formatEUR(result.net_profit)}
                      bold
                      color={result.net_profit >= 0 ? "#0F766E" : "#DC2626"}
                    />
                  </div>
                </div>

                {/* Fiscalidade + lucro pos-impostos (Melhoria 3) */}
                {totalTax > 0 && (
                  <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
                    <h3 className="text-sm font-semibold text-amber-700">Fiscalidade</h3>
                    {result.entity_structure !== "pf_only" && result.total_corporate_tax != null ? (
                      <>
                        {result.irc_taxable_income != null && <DetailRow label="Base tributável (JP)" value={formatEUR(result.irc_taxable_income)} />}
                        {result.irc_estimated != null && <DetailRow label="IRC (21%)" value={formatEUR(result.irc_estimated)} />}
                        {result.derrama_estimated != null && <DetailRow label="Derrama (1.5%)" value={formatEUR(result.derrama_estimated)} />}
                        <div className="border-t border-slate-300 pt-2">
                          <DetailRow label="Total impostos" value={formatEUR(result.total_corporate_tax)} bold color="#DC2626" />
                        </div>
                      </>
                    ) : result.capital_gains_tax != null ? (
                      <>
                        <DetailRow label="Mais-valias (IRS)" value={formatEUR(result.capital_gains_tax)} />
                        <p className="text-xs text-slate-500">50% da mais-valia englobada no IRS progressivo</p>
                      </>
                    ) : null}
                    <div className="border-t border-teal-200 pt-3 mt-2">
                      <DetailRow label="Lucro bruto" value={formatEUR(result.net_profit)} />
                      <DetailRow label="Impostos estimados" value={`-${formatEUR(totalTax)}`} color="#DC2626" />
                      <DetailRow label="Lucro líquido (pós-impostos)" value={formatEUR(lucroPosImpostos)} bold color={lucroPosImpostos >= 0 ? "#0F766E" : "#DC2626"} />
                    </div>
                  </div>
                )}

                {/* Save scenario */}
                {!modelId && (
                  <button
                    onClick={() => {
                      setShowSaveModal(true);
                      // Carregar propriedades existentes
                      fetch(`${SUPABASE_URL}/rest/v1/properties?select=id,municipality,parish,asking_price,property_type,status&status=neq.descartado&order=created_at.desc&limit=50`, {
                        headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` },
                      }).then(r => { if (!r.ok) { console.error("Props fetch failed:", r.status); return []; } return r.json(); }).then(setExistingProperties).catch(e => console.error("Props error:", e));
                    }}
                    className="w-full bg-teal-700 text-white py-2.5 rounded-lg font-medium hover:bg-teal-800 transition-colors text-sm"
                  >
                    Salvar cenário com condições de pagamento
                  </button>
                )}
                {modelId && (
                  <div className="bg-green-50 rounded-lg p-3 text-sm text-green-700">
                    Cenario salvo (ID: {modelId.slice(0, 8)}...)
                  </div>
                )}
                {saveMsg && (
                  <p className={`text-sm ${saveMsg.includes("Erro") ? "text-red-600" : "text-green-600"}`}>{saveMsg}</p>
                )}
              </div>
              );
            })()}
          </div>

          {/* Scenarios */}
          {scenarios && scenarios.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <h2 className="text-lg font-semibold mb-4">Cenários</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {scenarios.map((sc) => {
                  const colors: Record<string, string> = {
                    conservative: "#DC2626",
                    base: "#D97706",
                    optimistic: "#16A34A",
                  };
                  const labels: Record<string, string> = {
                    conservative: "Conservador",
                    base: "Base",
                    optimistic: "Optimista",
                  };
                  const color = colors[sc.label] ?? "#94A3B8";
                  const label = labels[sc.label] ?? sc.label;
                  return (
                    <div key={sc.label} className="rounded-xl border border-slate-200 p-5 text-center">
                      <p className="text-sm font-bold mb-3" style={{ color }}>{label}</p>
                      <div className="space-y-3">
                        <div>
                          <p className="text-xs text-slate-500 uppercase">ROI</p>
                          <p className="text-xl font-bold text-slate-900">{(sc.roi_pct ?? 0).toFixed(1)}%</p>
                        </div>
                        <div>
                          <p className="text-xs text-slate-500 uppercase">Lucro</p>
                          <p className="text-lg font-bold text-slate-900">{formatEUR(sc.net_profit)}</p>
                        </div>
                        <div>
                          <p className="text-xs text-slate-500 uppercase">MAO</p>
                          <p className="text-lg font-bold text-slate-900">{formatEUR(sc.mao)}</p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Cash Flow Table */}
          {cashFlow && cashFlow.flows && cashFlow.flows.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <h2 className="text-lg font-semibold mb-4">Fluxo de Caixa Mensal</h2>

              {/* Summary KPIs */}
              <div className="grid grid-cols-2 gap-4 mb-6">
                <KpiCard label="Pico de caixa necessário" value={formatEUR(cashFlow.pico_caixa_necessario)} />
                <KpiCard label="Saldo final" value={formatEUR(cashFlow.saldo_final)} color={cashFlow.saldo_final >= 0 ? "#0F766E" : "#DC2626"} />
              </div>

              {/* Table */}
              <div className="cashflow-wrapper overflow-x-auto">
                <table className="cashflow-table w-full text-sm">
                  <thead>
                    <tr className="border-b-2 border-slate-200">
                      <th className="text-left py-2 px-2 text-teal-700 font-semibold text-xs">Periodo</th>
                      <th className="text-right py-2 px-2 text-teal-700 font-semibold text-xs">Saidas</th>
                      <th className="text-right py-2 px-2 text-teal-700 font-semibold text-xs">PMT</th>
                      <th className="text-right py-2 px-2 text-teal-700 font-semibold text-xs">Manut.</th>
                      <th className="text-right py-2 px-2 text-teal-700 font-semibold text-xs">Payoff</th>
                      <th className="text-right py-2 px-2 text-teal-700 font-semibold text-xs">Fluxo</th>
                      <th className="text-right py-2 px-2 text-teal-700 font-semibold text-xs">Acumulado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cashFlow.flows.map((f, i) => {
                      const catColor = CAT_COLORS[f.categoria] ?? "#94A3B8";
                      const saidas = (f.aquisicao ?? 0) + (f.obra ?? 0);
                      const isLast = i === cashFlow.flows.length - 1;
                      return (
                        <tr
                          key={i}
                          className={`border-b border-slate-100 ${isLast ? "font-bold" : ""}`}
                          style={{ borderLeft: `3px solid ${catColor}` }}
                        >
                          <td className="py-1.5 px-2 font-semibold text-xs">{f.label}</td>
                          <td className="py-1.5 px-2 text-right text-xs">{fmtCell(saidas)}</td>
                          <td className="py-1.5 px-2 text-right text-xs">{fmtCell(f.pmt ?? 0)}</td>
                          <td className="py-1.5 px-2 text-right text-xs">{fmtCell(f.manut ?? 0)}</td>
                          <td className="py-1.5 px-2 text-right text-xs">{fmtCell(f.payoff ?? 0)}</td>
                          <td className={`py-1.5 px-2 text-right text-xs font-medium ${f.fluxo < 0 ? "text-red-600" : "text-teal-700"}`}>
                            {fmtCell(f.fluxo)}
                          </td>
                          <td className={`py-1.5 px-2 text-right text-xs font-medium ${f.acumulado < 0 ? "text-red-600" : "text-teal-700"}`}>
                            {fmtCell(f.acumulado)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Legend */}
              <div className="flex gap-4 mt-4">
                {Object.entries(CAT_COLORS).map(([cat, color]) => (
                  <div key={cat} className="flex items-center gap-1.5">
                    <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: color }} />
                    <span className="text-xs text-slate-500 capitalize">{cat}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* === Projecao Salva === */}
          {savedProjection && (
            <div className="bg-white rounded-xl border-2 border-teal-300 p-6 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold text-teal-700">Projecao Financeira Salva</h2>
                <span className="text-xs text-slate-400">ID: {savedProjection.model_id?.slice(0, 8)}...</span>
              </div>
              <div className="bg-teal-50 rounded-lg p-4 space-y-2">
                <p className="text-xs font-semibold text-teal-700 uppercase">Timeline do deal</p>
                <div className="space-y-1 text-sm">
                  {savedProjection.tranches?.filter((t: any) => t.tipo !== "escritura").map((t: any, i: number) => (
                    <div key={i} className="flex items-center gap-2">
                      <span className="w-24 text-xs text-teal-600 font-mono">{t.data || ""}</span>
                      <span className="w-2 h-2 rounded-full bg-teal-500" />
                      <span className="text-slate-700">{t.descricao} — <strong>{formatEUR(t.valor)}</strong> ({t.pct}%)</span>
                    </div>
                  ))}
                  <div className="flex items-center gap-2">
                    <span className="w-24 text-xs text-blue-600 font-mono">{savedProjection.escritura_date}</span>
                    <span className="w-2 h-2 rounded-full bg-blue-500" />
                    <span className="text-slate-700">Escritura — <strong>{formatEUR(savedProjection.tranches?.find((t: any) => t.tipo === "escritura")?.valor)}</strong></span>
                  </div>
                  <div className="flex items-center gap-2 text-slate-400">
                    <span className="w-24 text-xs font-mono">+obra+hold</span>
                    <span className="w-2 h-2 rounded-full bg-amber-400" />
                    <span>Obra + Holding ({result?.holding_months ?? 9} meses)</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-24 text-xs text-green-600 font-mono">venda</span>
                    <span className="w-2 h-2 rounded-full bg-green-500" />
                    <span className="text-slate-700">Venda — <strong>{formatEUR(result?.caixa_closing)}</strong> liquido</span>
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-4 gap-3">
                <div className="bg-slate-50 rounded-lg p-3 text-center">
                  <p className="text-xs text-slate-500">TIR anual</p>
                  <p className="text-lg font-bold">{(savedProjection.tir_anual_pct ?? 0).toFixed(1)}%</p>
                </div>
                <div className="bg-slate-50 rounded-lg p-3 text-center">
                  <p className="text-xs text-slate-500">Lucro bruto</p>
                  <p className="text-lg font-bold text-teal-700">{formatEUR(savedProjection.net_profit)}</p>
                </div>
                <div className="bg-slate-50 rounded-lg p-3 text-center">
                  <p className="text-xs text-slate-500">Investimento</p>
                  <p className="text-lg font-bold">{formatEUR(savedProjection.total_investment)}</p>
                </div>
                <div className="bg-slate-50 rounded-lg p-3 text-center">
                  <p className="text-xs text-slate-500">Badge</p>
                  <p className="text-lg font-bold" style={{ color: savedProjection.go_nogo === "go" ? "#16A34A" : savedProjection.go_nogo === "marginal" ? "#D97706" : "#DC2626" }}>
                    {(savedProjection.go_nogo ?? "").toUpperCase()}
                  </p>
                </div>
              </div>
              <p className="text-xs text-slate-400">
                Projecao com {savedProjection.cash_flow?.flows?.length ?? 0} periodos persistida no Supabase.
              </p>
            </div>
          )}
        </>
      )}

      {/* ===== Cenários Salvos ===== */}
      {activeTab === "saved" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Cenários Salvos</h2>
            <button
              onClick={fetchSavedScenarios}
              disabled={scenariosLoading}
              className="px-4 py-2 bg-teal-700 text-white rounded-lg text-sm hover:bg-teal-800 disabled:opacity-50"
            >
              {scenariosLoading ? "A carregar..." : "Actualizar"}
            </button>
          </div>

          {savedScenarios.length === 0 && !scenariosLoading && (
            <div className="text-center py-8">
              <p className="text-slate-400">Nenhum cenário salvo.</p>
              <p className="text-sm text-slate-400 mt-1">Simule e clique em &ldquo;Salvar cenário&rdquo; para criar.</p>
            </div>
          )}

          {/* Lista de cenários */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {savedScenarios.map((sc: any) => (
              <div
                key={sc.id}
                className={`bg-white rounded-xl border-2 p-5 cursor-pointer transition-all hover:shadow-md ${
                  selectedScenario?.model_id === sc.id ? "border-teal-400" : "border-slate-200"
                }`}
                onClick={() => loadScenarioDetail(sc.id)}
              >
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <p className="font-semibold text-slate-900">{sc.scenario_name || "base"}</p>
                    <p className="text-xs text-slate-400">
                      {sc.created_at ? new Date(sc.created_at).toLocaleString("pt-PT", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : ""}
                    </p>
                    {sc.properties && (
                      <p className="text-xs text-teal-600 mt-0.5">
                        {sc.properties.municipality || ""}{sc.properties.parish ? ` — ${sc.properties.parish}` : ""} {sc.properties.property_type ? `(${sc.properties.property_type})` : ""}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className="px-3 py-1 rounded-lg text-sm font-bold text-white"
                      style={{ backgroundColor: sc.go_nogo === "go" ? "#16A34A" : sc.go_nogo === "marginal" ? "#D97706" : "#DC2626" }}
                    >
                      {(sc.go_nogo ?? "").toUpperCase()}
                    </span>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDeleteScenario(sc.id); }}
                      className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                      title="Excluir cenário"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
                    </button>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2 text-sm">
                  <div>
                    <p className="text-xs text-slate-500">Compra</p>
                    <p className="font-medium">{formatEUR(sc.purchase_price)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Venda</p>
                    <p className="font-medium">{formatEUR(sc.estimated_sale_price)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Lucro</p>
                    <p className="font-medium text-teal-700">{formatEUR(sc.net_profit)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">TIR</p>
                    <p className="font-medium">{(sc.tir_anual_pct ?? 0).toFixed(1)}%</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">ROI</p>
                    <p className="font-medium">{(sc.roi_pct ?? 0).toFixed(1)}%</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Investimento</p>
                    <p className="font-medium">{formatEUR(sc.total_investment)}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Detalhe do cenário seleccionado */}
          {selectedScenario && (
            <div className="bg-white rounded-xl border-2 border-teal-300 p-6 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold text-teal-700">Detalhe do cenário</h3>
                <button
                  onClick={() => { setShowCfpModal(true); loadCfpProjects(); }}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
                >
                  Exportar para CashFlow Pro
                </button>
              </div>

              {/* Condições de pagamento */}
              {selectedScenario.payment_condition && (
                <div className="bg-teal-50 rounded-lg p-4 space-y-2">
                  <p className="text-xs font-semibold text-teal-700 uppercase">Condições de pagamento</p>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <p className="text-xs text-teal-600">Data CPCV</p>
                      <p className="font-medium">{selectedScenario.payment_condition.cpcv_date?.slice(0, 10)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-teal-600">Data escritura</p>
                      <p className="font-medium">{selectedScenario.payment_condition.escritura_date?.slice(0, 10)}</p>
                    </div>
                  </div>
                  {selectedScenario.payment_condition.tranches?.map((t: any, i: number) => (
                    <div key={i} className="flex items-center gap-2 text-sm">
                      <span className="w-2 h-2 rounded-full" style={{ backgroundColor: t.tipo === "escritura" ? "#2563EB" : "#14B8A6" }} />
                      <span className="font-medium">{t.descricao}</span>
                      <span className="text-slate-500">{t.pct}%</span>
                      <span className="text-teal-700 font-medium">{formatEUR(t.valor)}</span>
                      <span className="text-xs text-slate-400">{t.data}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Projecção mensal */}
              {selectedScenario.projections?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase mb-2">Projecção mensal ({selectedScenario.projections.length} períodos)</p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b-2 border-slate-200">
                          <th className="text-left py-2 px-2 text-xs font-semibold text-teal-700">Período</th>
                          <th className="text-right py-2 px-2 text-xs font-semibold text-teal-700">Projetado</th>
                          <th className="text-right py-2 px-2 text-xs font-semibold text-teal-700">Real</th>
                          <th className="text-right py-2 px-2 text-xs font-semibold text-teal-700">Acumulado</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedScenario.projections.map((p: any, i: number) => (
                          <tr key={i} className="border-b border-slate-100">
                            <td className="py-1.5 px-2 text-xs font-medium">{p.periodo_label}</td>
                            <td className={`py-1.5 px-2 text-right text-xs ${p.fluxo_projetado < 0 ? "text-red-600" : "text-teal-700"}`}>
                              {p.fluxo_projetado?.toLocaleString("pt-PT", { maximumFractionDigits: 0 }) ?? "-"}
                            </td>
                            <td className="py-1.5 px-2 text-right text-xs text-slate-400">
                              {p.fluxo_real != null ? p.fluxo_real.toLocaleString("pt-PT", { maximumFractionDigits: 0 }) : "—"}
                            </td>
                            <td className={`py-1.5 px-2 text-right text-xs font-medium ${p.acumulado_projetado < 0 ? "text-red-600" : "text-teal-700"}`}>
                              {p.acumulado_projetado?.toLocaleString("pt-PT", { maximumFractionDigits: 0 }) ?? "-"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* === Modal de save com condicoes de pagamento === */}
      {showSaveModal && result && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6 space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-900">Salvar cenário com condições de pagamento</h2>
              <button onClick={() => setShowSaveModal(false)} className="text-slate-400 hover:text-slate-600 text-xl">&times;</button>
            </div>

            {/* Seccao 1: Identificacao */}
            <div className="space-y-3">
              <p className="text-xs font-semibold text-slate-500 uppercase">Identificacao</p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-sm font-medium text-slate-700">Vincular a imóvel</label>
                    <button
                      type="button"
                      onClick={() => setShowNewProperty(!showNewProperty)}
                      className="text-xs text-teal-600 hover:text-teal-800 font-medium"
                    >
                      {showNewProperty ? "Seleccionar existente" : "+ Criar novo imóvel"}
                    </button>
                  </div>

                  {!showNewProperty ? (
                    <>
                      <select
                        value={selectedPropertyId}
                        onChange={(e) => setSelectedPropertyId(e.target.value)}
                        className={`w-full border rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-teal-500 ${!selectedPropertyId ? "border-red-300" : "border-slate-300"}`}
                      >
                        <option value="">-- Seleccionar imóvel --</option>
                        {existingProperties.map((p: any) => (
                          <option key={p.id} value={p.id}>
                            {p.municipality || "?"}{p.parish ? ` — ${p.parish}` : ""} | {p.property_type || ""} | {formatEUR(p.asking_price)}{p.financial_models?.length ? " (já tem cenário)" : ""}
                          </option>
                        ))}
                      </select>
                      {!selectedPropertyId && <p className="text-xs text-red-500 mt-0.5">Obrigatório</p>}
                      {selectedPropertyId && existingProperties.find((p: any) => p.id === selectedPropertyId)?.financial_models?.length > 0 && (
                        <p className="text-xs text-amber-600 mt-0.5">Este imóvel já tem cenário(s). O novo será adicionado, mantendo os existentes.</p>
                      )}
                    </>
                  ) : (
                    <div className="border border-teal-200 rounded-lg p-3 bg-teal-50 space-y-2">
                      <div className="grid grid-cols-2 gap-2">
                        <input id="new_prop_municipality" type="text" placeholder="Concelho (ex: Lisboa)" className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
                        <input id="new_prop_parish" type="text" placeholder="Freguesia (opcional)" className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <select id="new_prop_type" className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm bg-white outline-none focus:ring-2 focus:ring-teal-500">
                          <option value="apartment">Apartamento</option>
                          <option value="house">Moradia</option>
                          <option value="building">Prédio</option>
                          <option value="land">Terreno</option>
                          <option value="commercial">Comercial</option>
                        </select>
                        <input id="new_prop_price" type="number" placeholder="Preço pedido (€)" className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
                      </div>
                      <button
                        type="button"
                        disabled={newPropLoading}
                        onClick={async () => {
                          const municipality = (document.getElementById("new_prop_municipality") as HTMLInputElement).value;
                          if (!municipality) { alert("Preencha pelo menos o concelho."); return; }
                          setNewPropLoading(true);
                          try {
                            const res = await fetch(`${API_BASE}/api/v1/financial/create-property`, {
                              method: "POST",
                              headers: { "Content-Type": "application/json" },
                              body: JSON.stringify({
                                municipality,
                                parish: (document.getElementById("new_prop_parish") as HTMLInputElement).value || null,
                                property_type: (document.getElementById("new_prop_type") as HTMLSelectElement).value,
                                asking_price: parseFloat((document.getElementById("new_prop_price") as HTMLInputElement).value) || null,
                              }),
                            });
                            if (res.ok) {
                              const prop = await res.json();
                              setExistingProperties((prev) => [prop, ...prev]);
                              setSelectedPropertyId(prop.id);
                              setShowNewProperty(false);
                            } else {
                              const err = await res.json().catch(() => null);
                              alert(`Erro: ${err?.detail || "Falha ao criar imóvel"}`);
                            }
                          } catch { alert("Erro de comunicação."); }
                          setNewPropLoading(false);
                        }}
                        className="w-full bg-teal-600 text-white py-1.5 rounded-lg text-sm font-medium hover:bg-teal-700 disabled:opacity-50 transition-colors"
                      >
                        {newPropLoading ? "A criar..." : "Criar imóvel e vincular"}
                      </button>
                    </div>
                  )}
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Nome do cenario</label>
                  <input
                    type="text"
                    value={scenarioName}
                    onChange={(e) => setScenarioName(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500"
                  />
                </div>
              </div>
            </div>

            {/* Seccao 2: Condições de pagamento */}
            <div className="space-y-3">
              <p className="text-xs font-semibold text-slate-500 uppercase">Condições de pagamento</p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Data CPCV</label>
                  <input
                    type="date"
                    value={cpcvDate}
                    onChange={(e) => setCpcvDate(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Data escritura prevista</label>
                  <input
                    type="date"
                    value={escrituraDate}
                    onChange={(e) => setEscrituraDate(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500"
                  />
                </div>
              </div>

              {/* Tabela de tranches */}
              <div className="bg-slate-50 rounded-lg p-4 space-y-3">
                <p className="text-sm font-semibold text-slate-700">Tranches de pagamento</p>
                <div className="space-y-2">
                  {tranches.map((t, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <input
                        type="text"
                        value={t.descricao}
                        onChange={(e) => { const next = [...tranches]; next[i].descricao = e.target.value; setTranches(next); }}
                        className="flex-1 border border-slate-300 rounded px-2 py-1.5 text-sm"
                        placeholder="Descricao"
                      />
                      <input
                        type="number"
                        value={t.pct}
                        onChange={(e) => { const next = [...tranches]; next[i].pct = Number(e.target.value); setTranches(next); }}
                        className="w-20 border border-slate-300 rounded px-2 py-1.5 text-sm text-right"
                        step="any"
                      />
                      <span className="text-sm text-slate-500">%</span>
                      <span className="text-sm text-slate-700 w-24 text-right">
                        {formatEUR(Math.round((lastPayload?.purchase_price ?? 0) * t.pct / 100))}
                      </span>
                      <input
                        type="number"
                        value={t.dias_apos_cpcv}
                        onChange={(e) => { const next = [...tranches]; next[i].dias_apos_cpcv = Number(e.target.value); setTranches(next); }}
                        className="w-16 border border-slate-300 rounded px-2 py-1.5 text-sm text-right"
                      />
                      <span className="text-xs text-slate-400">dias</span>
                      <button
                        onClick={() => setTranches(tranches.filter((_, j) => j !== i))}
                        className="text-red-400 hover:text-red-600 text-sm px-1"
                      >
                        &times;
                      </button>
                    </div>
                  ))}
                </div>

                {/* Linha escritura (auto-calculada) */}
                {(() => {
                  const somaPct = tranches.reduce((s, t) => s + t.pct, 0);
                  const restPct = Math.max(100 - somaPct, 0);
                  return (
                    <div className="flex items-center gap-2 text-sm text-slate-500 border-t border-slate-200 pt-2">
                      <span className="flex-1 italic">Escritura (auto)</span>
                      <span className="w-20 text-right font-medium">{restPct.toFixed(0)}</span>
                      <span>%</span>
                      <span className="w-24 text-right font-medium">{formatEUR(Math.round((lastPayload?.purchase_price ?? 0) * restPct / 100))}</span>
                      <span className="w-16" />
                      <span className="text-xs" />
                      <span className="px-1" />
                    </div>
                  );
                })()}

                <div className="flex items-center justify-between">
                  <button
                    onClick={() => setTranches([...tranches, { descricao: `Tranche ${tranches.length + 1}`, tipo: "tranche_intermedia", pct: 5, dias_apos_cpcv: (tranches.length + 1) * 30 }])}
                    className="text-sm text-teal-600 hover:text-teal-800"
                  >
                    + Adicionar tranche
                  </button>
                  <span className="text-sm font-medium text-slate-700">
                    Total: {(tranches.reduce((s, t) => s + t.pct, 0) + Math.max(100 - tranches.reduce((s, t) => s + t.pct, 0), 0)).toFixed(0)}% = {formatEUR(lastPayload?.purchase_price ?? 0)}
                  </span>
                </div>
              </div>
            </div>

            {/* Seccao 3: Resumo */}
            <div className="bg-teal-50 rounded-lg p-4 space-y-2">
              <p className="text-xs font-semibold text-teal-700 uppercase">Resumo</p>
              <div className="grid grid-cols-4 gap-3 text-sm">
                <div>
                  <p className="text-xs text-teal-600">Margem bruta</p>
                  <p className="font-bold">{result.roi_simple_pct?.toFixed(1)}%</p>
                </div>
                <div>
                  <p className="text-xs text-teal-600">TIR anual</p>
                  <p className="font-bold">{(result.tir_anual_pct ?? result.roi_pct ?? 0).toFixed(1)}%</p>
                </div>
                <div>
                  <p className="text-xs text-teal-600">Lucro bruto</p>
                  <p className="font-bold">{formatEUR(result.net_profit)}</p>
                </div>
                <div>
                  <p className="text-xs text-teal-600">Badge</p>
                  <p className="font-bold" style={{ color: result.go_nogo === "go" ? "#16A34A" : result.go_nogo === "marginal" ? "#D97706" : "#DC2626" }}>
                    {(result.go_nogo ?? "pending").toUpperCase()}
                  </p>
                </div>
              </div>
            </div>

            {/* Botao salvar */}
            <button
              onClick={handleSaveScenario}
              disabled={saveLoading || !cpcvDate || !escrituraDate}
              className="w-full bg-teal-700 text-white py-3 rounded-lg font-medium hover:bg-teal-800 disabled:opacity-50 transition-colors"
            >
              {saveLoading ? "A salvar..." : "Salvar e gerar projecao financeira"}
            </button>
            {saveMsg && (
              <p className={`text-sm ${saveMsg.includes("Erro") ? "text-red-600" : "text-green-600"}`}>{saveMsg}</p>
            )}
          </div>
        </div>
      )}

      {/* Modal CashFlow Pro — seleccao de projecto */}
      {showCfpModal && selectedScenario && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-900">Exportar para CashFlow Pro</h2>
              <button onClick={() => setShowCfpModal(false)} className="text-slate-400 hover:text-slate-600 text-xl">&times;</button>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Projecto CashFlow Pro</label>
              <select
                value={cfpProjectId}
                onChange={(e) => setCfpProjectId(e.target.value)}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">-- Sem projecto (geral) --</option>
                {cfpProjects.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
              <p className="text-xs text-slate-400 mt-1">Seleccione o projecto onde os lançamentos serão criados.</p>
            </div>

            <button
              onClick={async () => {
                setCfpExporting(true);
                try {
                  const res = await fetch(`${API_BASE}/api/v1/financial/${selectedScenario.model_id}/export-cashflow`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ project_id: cfpProjectId || null }),
                  });
                  if (res.ok) {
                    const data = await res.json();
                    const ins = data.inserted_count ?? 0;
                    const upd = data.updated_count ?? 0;
                    alert(`Exportado para CashFlow Pro!\n${ins} lançamentos criados, ${upd} actualizados.`);
                    setShowCfpModal(false);
                  } else {
                    const err = await res.json().catch(() => null);
                    alert(`Erro: ${err?.detail || "Falha na exportação"}`);
                  }
                } catch { alert("Erro de comunicação."); }
                setCfpExporting(false);
              }}
              disabled={cfpExporting}
              className="w-full bg-blue-600 text-white py-2.5 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {cfpExporting ? "A exportar..." : "Exportar lançamentos"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function fmtCell(v: number): string {
  if (v === 0) return "-";
  return v.toLocaleString("pt-PT", { maximumFractionDigits: 0 });
}

function Field({
  name,
  label,
  placeholder,
  type = "number",
}: {
  name: string;
  label: string;
  placeholder: string;
  type?: string;
}) {
  return (
    <div className="form-field">
      <label className="block text-sm font-medium text-slate-700 mb-1">{label}</label>
      <input
        name={name}
        type={type}
        placeholder={placeholder}
        step={type === "number" ? "any" : undefined}
        className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-500 focus:border-teal-500 outline-none"
      />
    </div>
  );
}

function KpiCard({
  label,
  value,
  color,
  tooltip,
}: {
  label: string;
  value: string;
  color?: string;
  tooltip?: string;
}) {
  return (
    <div className="bg-slate-50 rounded-lg p-4 relative group">
      <div className="flex items-center gap-1">
        <p className="metric-label text-xs text-slate-500 uppercase tracking-wider">{label}</p>
        {tooltip && (
          <span className="text-slate-400 cursor-help text-xs" title={tooltip}>i</span>
        )}
      </div>
      <p className="metric-value text-xl font-bold mt-1" style={{ color: color ?? "#0F172A" }}>
        {value}
      </p>
      {tooltip && (
        <div className="hidden group-hover:block absolute z-10 bottom-full left-0 mb-2 w-72 bg-white border border-slate-200 rounded-lg shadow-lg p-3 text-xs text-slate-600 leading-relaxed">
          {tooltip}
        </div>
      )}
    </div>
  );
}

function DetailRow({
  label,
  value,
  bold,
  color,
}: {
  label: string;
  value: string;
  bold?: boolean;
  color?: string;
}) {
  return (
    <div className="investment-row items-center py-1">
      <span className={`label text-sm ${bold ? "font-bold" : ""} text-slate-600`}>{label}</span>
      <span className={`value text-sm ${bold ? "font-bold" : "font-medium"}`} style={{ color: color ?? "#0F172A" }}>
        {value}
      </span>
    </div>
  );
}
