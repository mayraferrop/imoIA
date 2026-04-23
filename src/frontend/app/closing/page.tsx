"use client";

import { useState, useEffect } from "react";
import useSWR, { mutate as globalMutate } from "swr";
import { apiPost, apiPatch, apiPut } from "@/lib/api";
import { formatEUR, cn } from "@/lib/utils";

const CLOSINGS_KEY = "/api/v1/closing";
const DEALS_KEY = "/api/v1/deals/?limit=100";
const PORTFOLIO_KEY = "/api/v1/portfolio/summary";

interface Closing {
  id: string;
  deal_id?: string;
  property_id?: string;
  closing_type: string;
  status: string;
  transaction_price?: number;
  cpcv_date?: string;
  deed_actual_date?: string;
  registration_date?: string;
  imt_guide_expires_at?: string;
  is_guide_expires_at?: string;
  checklist?: Record<string, { label: string; done: boolean; order: number }>;
  checklist_progress?: { done: number; total: number; pct: number };
}

interface PnlData {
  status?: string;
  purchase_price?: number;
  sale_price?: number;
  imt_cost?: number;
  is_cost?: number;
  renovation_budget?: number;
  renovation_actual?: number;
  sale_commission?: number;
  estimated_profit?: number;
  net_profit?: number;
  profit_variance?: number;
  roi_annualized_pct?: number;
  roi_variance_pct?: number;
  estimated_roi_pct?: number;
  moic?: number;
  profit_margin_pct?: number;
}

interface PortfolioSummary {
  total_deals?: number;
  total_invested?: number;
  total_profit?: number;
  avg_roi_pct?: number;
  deals?: PortfolioDeal[];
  best_deal?: PortfolioDeal;
  worst_deal?: PortfolioDeal;
}

interface PortfolioDeal {
  property_name?: string;
  purchase_price?: number;
  sale_price?: number;
  net_profit?: number;
  roi_annualized_pct?: number;
  moic?: number;
  holding_months?: number;
}

interface FiscalReport {
  total_capital_gains?: number;
  total_deductible_expenses?: number;
  taxable_amount?: number;
  estimated_tax?: number;
  deals?: any[];
}

const STATUS_LABELS: Record<string, [string, string]> = {
  pending: ["Pendente", "#94A3B8"],
  imt_paid: ["IMT Pago", "#D97706"],
  deed_scheduled: ["Escritura Agendada", "#2563EB"],
  deed_done: ["Escritura Realizada", "#7C3AED"],
  registered: ["Registado", "#06B6D4"],
  completed: ["Concluído", "#16A34A"],
  cancelled: ["Cancelado", "#DC2626"],
};

const STEPS = ["pending", "imt_paid", "deed_scheduled", "deed_done", "registered", "completed"];

const TRANSITIONS: Record<string, string[]> = {
  pending: ["imt_paid", "cancelled"],
  imt_paid: ["deed_scheduled", "cancelled"],
  deed_scheduled: ["deed_done", "cancelled"],
  deed_done: ["registered", "completed", "cancelled"],
  registered: ["completed", "cancelled"],
  cancelled: ["pending"],
};

export default function ClosingPage() {
  const [activeTab, setActiveTab] = useState<"fecho" | "pnl" | "portfolio" | "fiscal">("fecho");
  const [expandedClosing, setExpandedClosing] = useState<string | null>(null);

  // Create closing
  const [showCreate, setShowCreate] = useState(false);
  const [createDealId, setCreateDealId] = useState("");
  const [createType, setCreateType] = useState("compra");
  const [createPrice, setCreatePrice] = useState(0);

  // P&L
  const [pnlDealId, setPnlDealId] = useState("");
  const [pnlSalePrice, setPnlSalePrice] = useState(0);
  const [pnlMonths, setPnlMonths] = useState(0);

  // Fiscal
  const [fiscalYear, setFiscalYear] = useState(new Date().getFullYear());

  // SWR: always-loaded data
  const { data: closingsData, isLoading: closingsLoading } = useSWR<Closing[] | null>(CLOSINGS_KEY);
  const { data: dealsResp, isLoading: dealsLoading } = useSWR<{ items: any[] } | null>(DEALS_KEY);
  const closings = closingsData ?? [];
  const deals = (dealsResp?.items ?? []).map((d: any) => ({
    id: d.id,
    title: d.title ?? d.id.slice(0, 8),
    property_id: d.property_id,
  }));
  const loading = closingsLoading || dealsLoading;

  // Default first deal as selection when deals arrive
  useEffect(() => {
    if (deals.length > 0) {
      if (!createDealId) setCreateDealId(deals[0].id);
      if (!pnlDealId) setPnlDealId(deals[0].id);
    }
  }, [deals, createDealId, pnlDealId]);

  // Conditional SWR: P&L / Portfolio / Fiscal
  const pnlKey = activeTab === "pnl" && pnlDealId ? `/api/v1/pnl/${pnlDealId}` : null;
  const fiscalKey = activeTab === "fiscal" ? `/api/v1/portfolio/fiscal-report?year=${fiscalYear}` : null;

  const { data: pnlData, mutate: mutatePnl } = useSWR<PnlData | null>(pnlKey);
  const { data: portfolio } = useSWR<PortfolioSummary | null>(
    activeTab === "portfolio" ? PORTFOLIO_KEY : null
  );
  const { data: fiscalReport } = useSWR<FiscalReport | null>(fiscalKey);

  const refreshClosings = () => globalMutate(CLOSINGS_KEY);

  // Write operations
  async function createClosing() {
    if (!createDealId) return;
    const dealData = deals.find((d) => d.id === createDealId);
    const result = await apiPost("/api/v1/closing", {
      deal_id: createDealId,
      property_id: dealData?.property_id ?? "",
      closing_type: createType,
      transaction_price: createPrice > 0 ? createPrice : null,
    });
    if (result) {
      setShowCreate(false);
      refreshClosings();
    }
  }

  async function advanceStatus(closingId: string, targetStatus: string, extra?: { deed_scheduled_date?: string }) {
    if (extra?.deed_scheduled_date) {
      await apiPut(`/api/v1/closing/${closingId}`, { deed_scheduled_date: extra.deed_scheduled_date });
    }
    await apiPatch(`/api/v1/closing/${closingId}/status`, { target_status: targetStatus });
    refreshClosings();
  }

  async function toggleChecklist(closingId: string, key: string, done: boolean) {
    await apiPatch(`/api/v1/closing/${closingId}/checklist/${key}?done=${done}`);
    refreshClosings();
  }

  async function emitTaxGuide(closingId: string, guideType: string, amount: number) {
    if (amount <= 0) return;
    await apiPost(`/api/v1/closing/${closingId}/tax-guide`, { guide_type: guideType, amount });
    refreshClosings();
  }

  async function notifyPreference(closingId: string, entitiesStr: string) {
    const entities = entitiesStr.split(",").map((e) => e.trim()).filter(Boolean);
    if (entities.length === 0) return;
    await apiPost(`/api/v1/closing/${closingId}/preference-right`, { entities });
    refreshClosings();
  }

  async function calculatePnl() {
    if (!pnlDealId) return;
    await apiPost(`/api/v1/pnl/${pnlDealId}/calculate?sale_price=${pnlSalePrice}&holding_months=${pnlMonths}`);
    mutatePnl();
  }

  async function finalizePnl() {
    if (!pnlDealId) return;
    await apiPost(`/api/v1/pnl/${pnlDealId}/finalize`);
    mutatePnl();
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-slate-900">M9 — Fecho + P&L</h1>
        <div className="text-center py-16 text-slate-400">A carregar...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">M9 — Fecho + P&L</h1>
        <p className="text-sm text-slate-500 mt-1">Workflow de fecho e análise de rentabilidade real vs estimada</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-slate-200">
        {(
          [
            ["fecho", "Processos de Fecho"],
            ["pnl", "P&L Comparativo"],
            ["portfolio", "Portfolio"],
            ["fiscal", "Relatório Fiscal"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={cn(
              "px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors",
              activeTab === key
                ? "border-teal-700 text-teal-700"
                : "border-transparent text-slate-500 hover:text-slate-700"
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ===== TAB 1: Processos de Fecho ===== */}
      {activeTab === "fecho" && (
        <div className="space-y-4">
          {/* Create button */}
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <button
              onClick={() => setShowCreate(!showCreate)}
              className="w-full px-5 py-3 flex items-center justify-between hover:bg-slate-50 text-sm font-medium text-slate-600"
            >
              Criar processo de fecho
              <svg className={cn("w-4 h-4 text-slate-400 transition-transform", showCreate && "rotate-180")}
                fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {showCreate && (
              <div className="px-5 pb-5 border-t border-slate-100 pt-4 space-y-4">
                {deals.length === 0 ? (
                  <p className="text-sm text-slate-400">Nenhum deal encontrado. Crie um deal no M4 primeiro.</p>
                ) : (
                  <>
                    <div className="grid grid-cols-3 gap-4">
                      <div>
                        <label className="block text-xs text-slate-500 mb-1">Deal</label>
                        <select value={createDealId} onChange={(e) => setCreateDealId(e.target.value)}
                          className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500">
                          {deals.map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs text-slate-500 mb-1">Tipo</label>
                        <div className="flex gap-2 mt-1">
                          {["compra", "venda"].map((t) => (
                            <button
                              key={t}
                              onClick={() => setCreateType(t)}
                              className={cn(
                                "flex-1 px-3 py-2 text-sm rounded-lg border transition-colors",
                                createType === t
                                  ? "bg-teal-700 text-white border-teal-700"
                                  : "border-slate-200 text-slate-600 hover:bg-slate-50"
                              )}
                            >
                              {t === "compra" ? "Compra" : "Venda"}
                            </button>
                          ))}
                        </div>
                      </div>
                      <div>
                        <label className="block text-xs text-slate-500 mb-1">Preço transacção (EUR)</label>
                        <input type="number" value={createPrice} onChange={(e) => setCreatePrice(Number(e.target.value))}
                          className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" />
                      </div>
                    </div>
                    <button onClick={createClosing} className="px-4 py-2 bg-teal-700 text-white text-sm font-medium rounded-lg hover:bg-teal-800">
                      Criar Closing
                    </button>
                  </>
                )}
              </div>
            )}
          </div>

          {/* Closings list */}
          {closings.length === 0 ? (
            <div className="text-center py-12 text-slate-400">
              <p>Nenhum processo de fecho encontrado.</p>
            </div>
          ) : (
            closings.map((closing) => {
              const [statusLabel, statusColor] = STATUS_LABELS[closing.status] ?? [closing.status, "#94A3B8"];
              const cType = closing.closing_type === "compra" ? "Compra" : "Venda";
              const priceStr = closing.transaction_price ? formatEUR(closing.transaction_price) : "N/A";
              const isExpanded = expandedClosing === closing.id;

              // Progress
              const stepIdx = STEPS.indexOf(closing.status);
              const progressPct = stepIdx >= 0 ? (stepIdx / (STEPS.length - 1)) * 100 : 0;

              return (
                <div key={closing.id} className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                  <button
                    onClick={() => setExpandedClosing(isExpanded ? null : closing.id)}
                    className="w-full px-5 py-4 flex items-center justify-between hover:bg-slate-50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-semibold text-slate-900">{cType}</span>
                      <span className="text-sm text-slate-500">{priceStr}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span
                        className="text-xs font-medium px-2.5 py-1 rounded-full"
                        style={{ backgroundColor: `${statusColor}15`, color: statusColor }}
                      >
                        {statusLabel}
                      </span>
                      <svg
                        className={cn("w-4 h-4 text-slate-400 transition-transform", isExpanded && "rotate-180")}
                        fill="none" viewBox="0 0 24 24" stroke="currentColor"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </div>
                  </button>

                  {isExpanded && (
                    <div className="px-5 pb-5 border-t border-slate-100 pt-4 space-y-5">
                      {/* Progress bar */}
                      {closing.status !== "cancelled" && stepIdx >= 0 && (
                        <div>
                          <div className="flex justify-between text-xs text-slate-500 mb-1">
                            <span>{statusLabel}</span>
                            <span>{stepIdx + 1}/{STEPS.length}</span>
                          </div>
                          <div className="w-full bg-slate-100 rounded-full h-2">
                            <div
                              className="h-2 rounded-full transition-all"
                              style={{ width: `${progressPct}%`, backgroundColor: statusColor }}
                            />
                          </div>
                        </div>
                      )}
                      {closing.status === "cancelled" && (
                        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">Cancelado</div>
                      )}

                      {/* Key dates */}
                      <div className="grid grid-cols-3 gap-4">
                        {[
                          { label: "CPCV", value: closing.cpcv_date },
                          { label: "Escritura", value: closing.deed_actual_date },
                          { label: "Registo", value: closing.registration_date },
                        ].map((d) => (
                          <div key={d.label} className="bg-slate-50 rounded-lg p-3">
                            <p className="text-xs text-slate-500">{d.label}</p>
                            <p className="text-sm font-medium text-slate-900 mt-1">{d.value || "—"}</p>
                          </div>
                        ))}
                      </div>

                      {/* Tax guide alerts */}
                      {["imt", "is"].map((prefix) => {
                        const expiresStr = (closing as any)[`${prefix}_guide_expires_at`];
                        if (!expiresStr) return null;
                        const expires = new Date(expiresStr);
                        const hoursLeft = (expires.getTime() - Date.now()) / (1000 * 3600);
                        let alertClass = "bg-green-50 border-green-200 text-green-700";
                        let text = `Guia ${prefix.toUpperCase()}: ${hoursLeft.toFixed(0)}h restantes`;
                        if (hoursLeft < 0) {
                          alertClass = "bg-red-50 border-red-200 text-red-700";
                          text = `Guia ${prefix.toUpperCase()} EXPIRADA!`;
                        } else if (hoursLeft < 12) {
                          alertClass = "bg-yellow-50 border-yellow-200 text-yellow-700";
                          text = `Guia ${prefix.toUpperCase()} expira em ${hoursLeft.toFixed(0)}h!`;
                        }
                        return (
                          <div key={prefix} className={`border rounded-lg p-2 text-xs ${alertClass}`}>{text}</div>
                        );
                      })}

                      {/* Checklist */}
                      {closing.checklist && Object.keys(closing.checklist).length > 0 && (
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <h4 className="text-sm font-semibold text-slate-700">Checklist</h4>
                            <span className="text-xs text-slate-500">
                              {closing.checklist_progress?.done ?? 0}/{closing.checklist_progress?.total ?? 0} ({closing.checklist_progress?.pct ?? 0}%)
                            </span>
                          </div>
                          <div className="space-y-1">
                            {Object.entries(closing.checklist)
                              .sort(([, a], [, b]) => a.order - b.order)
                              .map(([key, item]) => (
                                <label key={key} className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer hover:bg-slate-50 px-2 py-1 rounded">
                                  <input
                                    type="checkbox"
                                    checked={item.done}
                                    onChange={() => toggleChecklist(closing.id, key, !item.done)}
                                    className="rounded border-slate-300 text-teal-700 focus:ring-teal-500"
                                  />
                                  <span className={item.done ? "line-through text-slate-400" : ""}>{item.label}</span>
                                </label>
                              ))}
                          </div>
                        </div>
                      )}

                      {/* Actions */}
                      <div className="grid grid-cols-3 gap-4 pt-2 border-t border-slate-100">
                        {/* Advance status */}
                        <ClosingAction
                          title="Avançar status"
                          closingId={closing.id}
                          status={closing.status}
                          onAdvance={advanceStatus}
                        />

                        {/* Tax guide */}
                        <TaxGuideAction closingId={closing.id} onEmit={emitTaxGuide} />

                        {/* Preference right */}
                        <PreferenceAction closingId={closing.id} onNotify={notifyPreference} />
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}

      {/* ===== TAB 2: P&L Comparativo ===== */}
      {activeTab === "pnl" && (
        <div className="space-y-4">
          {deals.length === 0 ? (
            <div className="text-center py-12 text-slate-400">Nenhum deal encontrado.</div>
          ) : (
            <>
              <div className="flex items-end gap-4">
                <div className="flex-1">
                  <label className="block text-xs text-slate-500 mb-1">Deal</label>
                  <select
                    value={pnlDealId}
                    onChange={(e) => setPnlDealId(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                  >
                    {deals.map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Preço venda</label>
                  <input type="number" value={pnlSalePrice} onChange={(e) => setPnlSalePrice(Number(e.target.value))}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Meses holding</label>
                  <input type="number" value={pnlMonths} onChange={(e) => setPnlMonths(Number(e.target.value))}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" />
                </div>
                <button onClick={calculatePnl} className="px-4 py-2 bg-teal-700 text-white text-sm font-medium rounded-lg hover:bg-teal-800 whitespace-nowrap">
                  Calcular P&L
                </button>
              </div>

              {!pnlData ? (
                <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-slate-400">
                  P&L não calculado para este deal. Use o botão acima.
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Metrics */}
                  <div className="grid grid-cols-4 gap-4">
                    {[
                      {
                        label: "ROI Anualizado",
                        value: `${(pnlData.roi_annualized_pct ?? 0).toFixed(1)}%`,
                        delta: pnlData.roi_variance_pct != null ? `${pnlData.roi_variance_pct > 0 ? "+" : ""}${pnlData.roi_variance_pct.toFixed(1)}%` : undefined,
                        deltaPositive: (pnlData.roi_variance_pct ?? 0) >= 0,
                      },
                      { label: "MOIC", value: `${(pnlData.moic ?? 0).toFixed(2)}x` },
                      {
                        label: "Lucro Líquido",
                        value: formatEUR(pnlData.net_profit),
                        delta: pnlData.profit_variance != null ? `${pnlData.profit_variance > 0 ? "+" : ""}${formatEUR(pnlData.profit_variance)}` : undefined,
                        deltaPositive: (pnlData.profit_variance ?? 0) >= 0,
                      },
                      { label: "Margem", value: `${(pnlData.profit_margin_pct ?? 0).toFixed(1)}%` },
                    ].map((m) => (
                      <div key={m.label} className="bg-white rounded-xl border border-slate-200 p-4">
                        <p className="text-xs text-slate-500">{m.label}</p>
                        <p className="text-xl font-bold text-slate-900 mt-1">{m.value}</p>
                        {m.delta && (
                          <p className={cn("text-xs mt-1", m.deltaPositive ? "text-green-600" : "text-red-600")}>
                            {m.delta}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* Comparison table */}
                  <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                    <h3 className="text-sm font-semibold text-slate-700 px-5 py-3 border-b border-slate-100">Estimado vs Real</h3>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-slate-50 text-xs text-slate-500">
                          <th className="text-left px-5 py-2 font-medium">Item</th>
                          <th className="text-right px-5 py-2 font-medium">Estimado</th>
                          <th className="text-right px-5 py-2 font-medium">Real</th>
                          <th className="text-right px-5 py-2 font-medium">Desvio</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[
                          { item: "Preço Compra", est: pnlData.purchase_price, real: pnlData.purchase_price },
                          { item: "IMT + IS", est: (pnlData.imt_cost ?? 0) + (pnlData.is_cost ?? 0), real: (pnlData.imt_cost ?? 0) + (pnlData.is_cost ?? 0) },
                          { item: "Obra (orçamento vs real)", est: pnlData.renovation_budget, real: pnlData.renovation_actual },
                          { item: "Preço Venda", est: pnlData.sale_price, real: pnlData.sale_price },
                          { item: "Comissão Venda", est: pnlData.sale_commission, real: pnlData.sale_commission },
                          { item: "Lucro Líquido", est: pnlData.estimated_profit, real: pnlData.net_profit },
                          { item: "ROI (%)", est: pnlData.estimated_roi_pct, real: pnlData.roi_annualized_pct },
                        ].map((row) => {
                          const estVal = row.est ?? 0;
                          const realVal = row.real ?? 0;
                          const deviation = realVal - estVal;
                          return (
                            <tr key={row.item} className="border-t border-slate-50 hover:bg-slate-50">
                              <td className="px-5 py-2 text-slate-700">{row.item}</td>
                              <td className="px-5 py-2 text-right text-slate-500">
                                {row.item.includes("ROI") ? `${estVal.toFixed(1)}%` : formatEUR(estVal)}
                              </td>
                              <td className="px-5 py-2 text-right font-medium text-slate-900">
                                {row.item.includes("ROI") ? `${realVal.toFixed(1)}%` : formatEUR(realVal)}
                              </td>
                              <td className={cn("px-5 py-2 text-right text-xs font-medium",
                                deviation > 0 ? "text-green-600" : deviation < 0 ? "text-red-600" : "text-slate-400"
                              )}>
                                {deviation > 0 ? "+" : ""}{row.item.includes("ROI") ? `${deviation.toFixed(1)}%` : formatEUR(deviation)}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>

                  {/* Finalize */}
                  {pnlData.status !== "final" ? (
                    <button onClick={finalizePnl} className="px-4 py-2 bg-teal-700 text-white text-sm font-medium rounded-lg hover:bg-teal-800">
                      Finalizar P&L
                    </button>
                  ) : (
                    <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-700">P&L finalizado</div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ===== TAB 3: Portfolio ===== */}
      {activeTab === "portfolio" && (
        <div className="space-y-4">
          {/* Summary metrics */}
          <div className="grid grid-cols-4 gap-4">
            {[
              { label: "Deals Fechados", value: portfolio?.total_deals ?? 0 },
              { label: "Total Investido", value: formatEUR(portfolio?.total_invested) },
              { label: "Lucro Total", value: formatEUR(portfolio?.total_profit) },
              { label: "ROI Médio", value: `${(portfolio?.avg_roi_pct ?? 0).toFixed(1)}%` },
            ].map((m) => (
              <div key={m.label} className="bg-white rounded-xl border border-slate-200 p-4">
                <p className="text-xs text-slate-500">{m.label}</p>
                <p className="text-xl font-bold text-slate-900 mt-1">{m.value}</p>
              </div>
            ))}
          </div>

          {portfolio?.deals && portfolio.deals.length > 0 ? (
            <>
              {/* ROI bar chart */}
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <h3 className="text-sm font-semibold text-slate-700 mb-4">ROI por Deal</h3>
                <div className="flex items-end gap-3 h-48">
                  {portfolio.deals.map((d, i) => {
                    const maxRoi = Math.max(...portfolio.deals!.map((dd) => Math.abs(dd.roi_annualized_pct ?? 0)), 1);
                    const roi = d.roi_annualized_pct ?? 0;
                    const heightPct = Math.abs(roi) / maxRoi * 100;
                    const color = roi >= 20 ? "#16A34A" : roi >= 0 ? "#F59E0B" : "#EF4444";
                    return (
                      <div key={i} className="flex-1 flex flex-col items-center justify-end h-full">
                        <span className="text-xs font-medium text-slate-700 mb-1">{roi.toFixed(1)}%</span>
                        <div
                          className="w-full rounded-t-md min-h-[4px]"
                          style={{ backgroundColor: color, height: `${heightPct}%` }}
                        />
                        <span className="text-[10px] text-slate-500 mt-1 truncate max-w-full text-center">
                          {d.property_name ?? `Deal ${i + 1}`}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Deals table */}
              <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                <h3 className="text-sm font-semibold text-slate-700 px-5 py-3 border-b border-slate-100">Detalhe por Deal</h3>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-slate-50 text-xs text-slate-500">
                      <th className="text-left px-5 py-2 font-medium">Propriedade</th>
                      <th className="text-right px-5 py-2 font-medium">Compra</th>
                      <th className="text-right px-5 py-2 font-medium">Venda</th>
                      <th className="text-right px-5 py-2 font-medium">Lucro</th>
                      <th className="text-right px-5 py-2 font-medium">ROI</th>
                      <th className="text-right px-5 py-2 font-medium">MOIC</th>
                      <th className="text-right px-5 py-2 font-medium">Meses</th>
                    </tr>
                  </thead>
                  <tbody>
                    {portfolio.deals.map((d, i) => (
                      <tr key={i} className="border-t border-slate-50 hover:bg-slate-50">
                        <td className="px-5 py-2 text-slate-700">{d.property_name ?? "—"}</td>
                        <td className="px-5 py-2 text-right text-slate-500">{formatEUR(d.purchase_price)}</td>
                        <td className="px-5 py-2 text-right text-slate-500">{formatEUR(d.sale_price)}</td>
                        <td className={cn("px-5 py-2 text-right font-medium", (d.net_profit ?? 0) >= 0 ? "text-green-600" : "text-red-600")}>
                          {formatEUR(d.net_profit)}
                        </td>
                        <td className="px-5 py-2 text-right text-slate-700">{(d.roi_annualized_pct ?? 0).toFixed(1)}%</td>
                        <td className="px-5 py-2 text-right text-slate-500">{(d.moic ?? 0).toFixed(2)}x</td>
                        <td className="px-5 py-2 text-right text-slate-500">{d.holding_months ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Best / Worst */}
              <div className="grid grid-cols-2 gap-4">
                {portfolio.best_deal && (
                  <div className="bg-green-50 border border-green-200 rounded-xl p-4">
                    <p className="text-xs text-green-600 font-semibold mb-1">Melhor deal</p>
                    <p className="text-sm text-green-800">
                      {portfolio.best_deal.property_name} — ROI {(portfolio.best_deal.roi_annualized_pct ?? 0).toFixed(1)}% — Lucro {formatEUR(portfolio.best_deal.net_profit)}
                    </p>
                  </div>
                )}
                {portfolio.worst_deal && (
                  <div className="bg-red-50 border border-red-200 rounded-xl p-4">
                    <p className="text-xs text-red-600 font-semibold mb-1">Pior deal</p>
                    <p className="text-sm text-red-800">
                      {portfolio.worst_deal.property_name} — ROI {(portfolio.worst_deal.roi_annualized_pct ?? 0).toFixed(1)}% — Lucro {formatEUR(portfolio.worst_deal.net_profit)}
                    </p>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="text-center py-12 text-slate-400">Nenhum deal com P&L calculado.</div>
          )}
        </div>
      )}

      {/* ===== TAB 4: Relatorio Fiscal ===== */}
      {activeTab === "fiscal" && (
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-slate-500 mb-1">Ano Fiscal</label>
            <select
              value={fiscalYear}
              onChange={(e) => setFiscalYear(Number(e.target.value))}
              className="w-48 px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
            >
              {Array.from({ length: 7 }, (_, i) => new Date().getFullYear() - i).map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>

          {/* Fiscal metrics */}
          <div className="grid grid-cols-4 gap-4">
            {[
              { label: "Mais-Valias Totais", value: formatEUR(fiscalReport?.total_capital_gains) },
              { label: "Despesas Dedutíveis", value: formatEUR(fiscalReport?.total_deductible_expenses) },
              { label: "Base Tributável (50%)", value: formatEUR(fiscalReport?.taxable_amount) },
              { label: "Imposto Estimado", value: formatEUR(fiscalReport?.estimated_tax) },
            ].map((m) => (
              <div key={m.label} className="bg-white rounded-xl border border-slate-200 p-4">
                <p className="text-xs text-slate-500">{m.label}</p>
                <p className="text-xl font-bold text-slate-900 mt-1">{m.value}</p>
              </div>
            ))}
          </div>

          {/* Fiscal deals table */}
          {fiscalReport?.deals && fiscalReport.deals.length > 0 ? (
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <h3 className="text-sm font-semibold text-slate-700 px-5 py-3 border-b border-slate-100">Detalhe por Deal</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-slate-50 text-xs text-slate-500">
                      {Object.keys(fiscalReport.deals[0] || {}).map((col) => (
                        <th key={col} className="text-left px-4 py-2 font-medium whitespace-nowrap">{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {fiscalReport.deals.map((deal: any, i: number) => (
                      <tr key={i} className="border-t border-slate-50 hover:bg-slate-50">
                        {Object.values(deal).map((val: any, j: number) => (
                          <td key={j} className="px-4 py-2 text-slate-700 whitespace-nowrap">
                            {typeof val === "number" ? (val > 100 ? formatEUR(val) : val.toFixed(1)) : String(val ?? "—")}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="text-center py-12 text-slate-400">Nenhum deal com P&L em {fiscalYear}.</div>
          )}
        </div>
      )}
    </div>
  );
}

/* ===== Sub-components for closing actions ===== */

function ClosingAction({ title, closingId, status, onAdvance }: {
  title: string; closingId: string; status: string;
  onAdvance: (id: string, target: string, extra?: { deed_scheduled_date?: string }) => void;
}) {
  const nextOpts = TRANSITIONS[status] ?? [];
  const [target, setTarget] = useState(nextOpts[0] ?? "");
  const [deedDate, setDeedDate] = useState("");

  useEffect(() => {
    setTarget(nextOpts[0] ?? "");
  }, [status]);

  if (nextOpts.length === 0) return <div />;

  const requiresDeedDate = target === "deed_scheduled";

  return (
    <div className="space-y-2">
      <label className="block text-xs text-slate-500">{title}</label>
      <select value={target} onChange={(e) => setTarget(e.target.value)}
        className="w-full px-3 py-2 border border-slate-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-teal-500">
        {nextOpts.map((o) => <option key={o} value={o}>{STATUS_LABELS[o]?.[0] ?? o}</option>)}
      </select>
      {requiresDeedDate && (
        <input
          type="date"
          value={deedDate}
          onChange={(e) => setDeedDate(e.target.value)}
          className="w-full px-3 py-2 border border-slate-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-teal-500"
          placeholder="Data escritura"
        />
      )}
      <button
        onClick={() => onAdvance(
          closingId,
          target,
          requiresDeedDate && deedDate ? { deed_scheduled_date: deedDate } : undefined,
        )}
        disabled={requiresDeedDate && !deedDate}
        className="w-full px-3 py-1.5 bg-teal-700 text-white text-xs font-medium rounded-lg hover:bg-teal-800 disabled:bg-slate-300 disabled:cursor-not-allowed"
      >
        Avançar
      </button>
    </div>
  );
}

function TaxGuideAction({ closingId, onEmit }: {
  closingId: string; onEmit: (id: string, type: string, amount: number) => void;
}) {
  const [guideType, setGuideType] = useState("imt");
  const [amount, setAmount] = useState(0);

  return (
    <div className="space-y-2">
      <label className="block text-xs text-slate-500">Emitir Guia</label>
      <select value={guideType} onChange={(e) => setGuideType(e.target.value)}
        className="w-full px-3 py-2 border border-slate-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-teal-500">
        <option value="imt">IMT</option>
        <option value="is">IS</option>
      </select>
      <input type="number" placeholder="Valor" value={amount || ""} onChange={(e) => setAmount(Number(e.target.value))}
        className="w-full px-3 py-2 border border-slate-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-teal-500" />
      <button
        onClick={() => onEmit(closingId, guideType, amount)}
        className="w-full px-3 py-1.5 text-xs font-medium text-teal-700 border border-teal-700 rounded-lg hover:bg-teal-50"
      >
        Emitir Guia
      </button>
    </div>
  );
}

function PreferenceAction({ closingId, onNotify }: {
  closingId: string; onNotify: (id: string, entities: string) => void;
}) {
  const [entities, setEntities] = useState("");

  return (
    <div className="space-y-2">
      <label className="block text-xs text-slate-500">Direito de Preferência</label>
      <input
        type="text"
        placeholder="Entidades (vírgula)"
        value={entities}
        onChange={(e) => setEntities(e.target.value)}
        className="w-full px-3 py-2 border border-slate-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-teal-500"
      />
      <button
        onClick={() => onNotify(closingId, entities)}
        className="w-full px-3 py-1.5 text-xs font-medium text-teal-700 border border-teal-700 rounded-lg hover:bg-teal-50"
      >
        Notificar
      </button>
    </div>
  );
}
