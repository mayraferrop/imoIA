"use client";

import { useState } from "react";
import { formatEUR, formatPercent, GRADE_COLORS } from "@/lib/utils";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

type Tab = "simulator" | "imt" | "mao";

const CAT_COLORS: Record<string, string> = {
  aquisicao: "#2563EB",
  obra: "#D97706",
  holding: "#94A3B8",
  venda: "#16A34A",
};

export default function FinancialPage() {
  const [activeTab, setActiveTab] = useState<Tab>("simulator");
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [saveLoading, setSaveLoading] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const [modelId, setModelId] = useState<string | null>(null);
  const [scenarios, setScenarios] = useState<ScenarioData[] | null>(null);
  const [lastPayload, setLastPayload] = useState<Record<string, any> | null>(null);

  // IMT
  const [imtResult, setImtResult] = useState<IMTResult | null>(null);
  const [imtLoading, setImtLoading] = useState(false);

  // MAO
  const [maoResult, setMaoResult] = useState<MAOResult | null>(null);
  const [maoLoading, setMaoLoading] = useState(false);

  async function handleSimulate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setResult(null);
    setModelId(null);
    setScenarios(null);
    setSaveMsg("");
    const fd = new FormData(e.currentTarget);

    const financingType = fd.get("financing_type") as string || "cash";
    const payload: Record<string, any> = {
      purchase_price: Number(fd.get("purchase_price")) || 295000,
      renovation_budget: Number(fd.get("renovation_cost")) || 0,
      estimated_sale_price: Number(fd.get("estimated_sale_price")) || 0,
      additional_holding_months: Number(fd.get("holding_months")) || 6,
      municipality: (fd.get("municipality") as string) || "Lisboa",
      property_type: fd.get("property_type") as string || "secondary",
      country: fd.get("country") as string || "PT",
      financing_type: financingType,
      renovation_duration_months: Number(fd.get("renovation_duration_months")) || 3,
      comissao_venda_pct: Number(fd.get("comissao_venda_pct")) || 6.15,
      monthly_condominio: Number(fd.get("monthly_condominio")) || 100,
      roi_target_pct: Number(fd.get("roi_target_pct")) || 15,
      scenario_name: "simulacao",
    };

    if (financingType !== "cash") {
      payload.loan_amount = Number(fd.get("loan_amount")) || 0;
      payload.interest_rate_pct = Number(fd.get("interest_rate_pct")) || 2.73;
      payload.loan_term_months = (Number(fd.get("loan_term_years")) || 30) * 12;
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
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveModel() {
    if (!lastPayload) return;
    setSaveLoading(true);
    setSaveMsg("");
    try {
      // Create temp property
      const propRes = await fetch(`${API_BASE}/api/v1/properties/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          property_type: "apartamento",
          asking_price: lastPayload.purchase_price,
          municipality: "Simulacao",
          notes: "Criado automaticamente pelo simulador M3",
          tags: ["simulacao"],
        }),
      });
      if (!propRes.ok) { setSaveMsg("Erro ao criar propriedade."); return; }
      const prop = await propRes.json();
      const propId = prop.id;

      // Save model
      const modelRes = await fetch(`${API_BASE}/api/v1/financial/?property_id=${propId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(lastPayload),
      });
      if (modelRes.ok) {
        const saved = await modelRes.json();
        if (saved.model_id) {
          setModelId(saved.model_id);
          setSaveMsg("Modelo guardado!");
          // Fetch scenarios
          fetchScenarios(saved.model_id);
        }
      } else {
        setSaveMsg("Erro ao guardar modelo.");
      }
    } catch {
      setSaveMsg("Erro de comunicacao.");
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
        ] as [Tab, string][]).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
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
          <h2 className="text-lg font-semibold mb-4">Calculo rapido de IMT</h2>
          <form onSubmit={handleIMT} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Field name="imt_value" label="Valor do imovel (EUR)" placeholder="295000" />
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Pais</label>
                <select name="imt_country" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-teal-500">
                  <option value="PT">Portugal</option>
                  <option value="BR">Brasil</option>
                </select>
              </div>
              <div className="flex items-end pb-2">
                <label className="flex items-center gap-2 text-sm text-slate-700">
                  <input type="checkbox" name="imt_hpp" className="rounded border-slate-300 text-teal-600 focus:ring-teal-500" />
                  HPP (habitacao propria)
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
              <Field name="mao_arv" label="ARV — Valor pos-obra (EUR)" placeholder="500000" />
              <Field name="mao_reno" label="Custo total de obra (EUR)" placeholder="100000" />
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
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Form */}
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <h2 className="text-lg font-semibold mb-4">Parametros</h2>
              <form onSubmit={handleSimulate} className="space-y-5">
                {/* Compra */}
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Compra</p>
                  <div className="grid grid-cols-2 gap-3">
                    <Field name="purchase_price" label="Preco de compra (EUR)" placeholder="295000" />
                    <Field name="municipality" label="Concelho" placeholder="Lisboa" type="text" />
                  </div>
                </div>

                {/* Obra */}
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Obra</p>
                  <div className="grid grid-cols-2 gap-3">
                    <Field name="renovation_cost" label="Orcamento obra (EUR)" placeholder="98400" />
                    <Field name="renovation_duration_months" label="Meses de obra" placeholder="3" />
                  </div>
                </div>

                {/* Financiamento */}
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Financiamento</p>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1">Tipo</label>
                      <select name="financing_type" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-teal-500">
                        <option value="cash">Cash</option>
                        <option value="mortgage">Credito</option>
                        <option value="mixed">Misto</option>
                      </select>
                    </div>
                    <Field name="loan_amount" label="Emprestimo (EUR)" placeholder="221250" />
                    <Field name="interest_rate_pct" label="TAN %" placeholder="2.73" />
                    <Field name="loan_term_years" label="Prazo (anos)" placeholder="30" />
                  </div>
                </div>

                {/* Venda */}
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Venda</p>
                  <div className="grid grid-cols-2 gap-3">
                    <Field name="estimated_sale_price" label="Preco venda / ARV (EUR)" placeholder="500000" />
                    <Field name="holding_months" label="Meses ate venda (apos obra)" placeholder="6" />
                    <Field name="comissao_venda_pct" label="Comissao venda + IVA %" placeholder="6.15" />
                    <Field name="monthly_condominio" label="Manutencao mensal (EUR)" placeholder="100" />
                  </div>
                </div>

                {/* Outros */}
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Outros</p>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1">Tipo imovel</label>
                      <select name="property_type" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-teal-500">
                        <option value="secondary">Secundario / investimento</option>
                        <option value="primary">HPP</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1">Pais</label>
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

            {/* Result */}
            {result && (
              <div className="space-y-6">
                {/* Go/No-Go badge + KPIs */}
                <div className="bg-white rounded-xl border border-slate-200 p-6">
                  <div className="flex items-center justify-between mb-6">
                    <h2 className="text-lg font-semibold">Resultado</h2>
                    <span
                      className="px-6 py-2 rounded-xl text-lg font-bold text-white"
                      style={{ backgroundColor: goNoGoColor }}
                    >
                      {goNoGoLabel}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <KpiCard
                      label="Lucro Liquido"
                      value={formatEUR(result.net_profit)}
                      color={result.net_profit >= 0 ? "#0F766E" : "#DC2626"}
                    />
                    <KpiCard label="MOIC" value={`${(result.moic ?? 0).toFixed(2)}x`} />
                    <KpiCard label="ROI" value={`${(result.roi_pct ?? 0).toFixed(1)}%`} />
                    <KpiCard label="Investimento Total" value={formatEUR(result.total_investment)} />
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

                {/* Detail cards */}
                <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
                  <h3 className="text-sm font-semibold text-teal-700">Custos de compra</h3>
                  <DetailRow label="IMT" value={formatEUR(result.imt)} />
                  <DetailRow label="Imposto de Selo" value={formatEUR(result.imposto_selo)} />
                  <DetailRow label="Escritura + Registo" value={formatEUR(result.notario_registo)} />
                  <div className="border-t border-slate-300 pt-2">
                    <DetailRow label="Total aquisicao" value={formatEUR(result.total_acquisition_cost)} bold />
                  </div>
                </div>

                {result.loan_amount != null && result.loan_amount > 0 && (
                  <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
                    <h3 className="text-sm font-semibold text-teal-700">Financiamento</h3>
                    <DetailRow label="Emprestimo" value={formatEUR(result.loan_amount)} />
                    <DetailRow label="PMT mensal" value={formatEUR(result.monthly_payment)} />
                    <DetailRow label={`Payoff mes ${result.holding_months ?? 0}`} value={formatEUR(result.payoff_at_sale)} />
                    <DetailRow label="Custos hipoteca" value={formatEUR(result.bank_fees)} />
                  </div>
                )}

                <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
                  <h3 className="text-sm font-semibold text-teal-700">Resultado</h3>
                  <DetailRow label="Caixa no closing" value={formatEUR(result.caixa_closing)} />
                  <DetailRow label="Caixa investido" value={`-${formatEUR(result.total_investment)}`} />
                  <div className="border-t border-slate-300 pt-2">
                    <DetailRow
                      label="Lucro (cash)"
                      value={formatEUR(result.net_profit)}
                      bold
                      color={result.net_profit >= 0 ? "#0F766E" : "#DC2626"}
                    />
                  </div>
                </div>

                {/* Save model */}
                {!modelId && (
                  <button
                    onClick={handleSaveModel}
                    disabled={saveLoading}
                    className="w-full bg-slate-100 text-slate-700 py-2.5 rounded-lg font-medium hover:bg-slate-200 disabled:opacity-50 transition-colors text-sm"
                  >
                    {saveLoading ? "A guardar..." : "Guardar modelo e ver cenarios + fluxo de caixa"}
                  </button>
                )}
                {saveMsg && (
                  <p className={`text-sm ${saveMsg.includes("Erro") ? "text-red-600" : "text-green-600"}`}>{saveMsg}</p>
                )}
              </div>
            )}
          </div>

          {/* Scenarios */}
          {scenarios && scenarios.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <h2 className="text-lg font-semibold mb-4">Cenarios</h2>
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
                <KpiCard label="Pico de caixa necessario" value={formatEUR(cashFlow.pico_caixa_necessario)} />
                <KpiCard label="Saldo final" value={formatEUR(cashFlow.saldo_final)} color={cashFlow.saldo_final >= 0 ? "#0F766E" : "#DC2626"} />
              </div>

              {/* Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
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
        </>
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
    <div>
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
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="bg-slate-50 rounded-lg p-4">
      <p className="text-xs text-slate-500 uppercase tracking-wider">{label}</p>
      <p className="text-xl font-bold mt-1" style={{ color: color ?? "#0F172A" }}>
        {value}
      </p>
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
    <div className="flex justify-between items-center py-1">
      <span className={`text-sm ${bold ? "font-bold" : ""} text-slate-600`}>{label}</span>
      <span className={`text-sm ${bold ? "font-bold" : "font-medium"}`} style={{ color: color ?? "#0F172A" }}>
        {value}
      </span>
    </div>
  );
}
