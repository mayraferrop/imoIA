"use client";

import { useEffect, useState } from "react";
import useSWR, { mutate as globalMutate } from "swr";
import { formatEUR } from "@/lib/utils";
import { apiGet, apiPost } from "@/lib/api";

/* ------------------------------------------------------------------ */
/*  Tipos locais                                                       */
/* ------------------------------------------------------------------ */

interface Deal {
  id: string;
  title?: string;
  status?: string;
  renovation_budget?: number;
}

interface Milestone {
  id: string;
  name: string;
  description?: string;
  status: string;
  budget: number;
  spent: number;
  completion_pct: number;
  supplier_name?: string;
}

interface Expense {
  id: string;
  description: string;
  amount: number;
  expense_date?: string;
  category: string;
  payment_method?: string;
  has_valid_invoice?: boolean;
  is_paid?: boolean;
}

interface Renovation {
  id: string;
  deal_id: string;
  deal_title?: string;
  status: string;
  initial_budget: number;
  current_budget?: number;
  total_spent: number;
  budget_variance_pct: number;
  progress_pct: number;
  contractor_name?: string;
  scope_description?: string;
  cashflow_project_id?: string;
  cashflow_project_name?: string;
  last_synced_at?: string;
}

interface RenovationDetail {
  renovation: Renovation;
  milestones: Milestone[];
  expense_summary?: {
    total_spent?: number;
    total_deductible?: number;
    total_non_deductible?: number;
  };
  budget_health?: string;
}

interface RenovationStats {
  active_count?: number;
  total_budget?: number;
  total_spent?: number;
  avg_progress?: number;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const MILESTONE_STATUS_ICONS: Record<string, string> = {
  pendente: "[ ]",
  em_curso: "[~]",
  concluido: "[ok]",
  bloqueado: "[x]",
};

const MILESTONE_STATUS_COLORS: Record<string, string> = {
  pendente: "bg-slate-100 text-slate-600",
  em_curso: "bg-blue-100 text-blue-700",
  concluido: "bg-green-100 text-green-700",
  bloqueado: "bg-red-100 text-red-700",
};

const EXPENSE_CATEGORIES = [
  { value: "material", label: "Material" },
  { value: "mao_de_obra", label: "Mão de obra" },
  { value: "equipamento", label: "Equipamento" },
  { value: "licenca", label: "Licença" },
  { value: "projecto", label: "Projecto" },
  { value: "outro", label: "Outro" },
];

const PAYMENT_METHODS = [
  { value: "transferencia", label: "Transferência" },
  { value: "cartao", label: "Cartão" },
  { value: "mbway", label: "MBWay" },
  { value: "cheque", label: "Cheque" },
  { value: "numerario", label: "Numerário" },
];

/* ================================================================== */
/*  PAGE                                                               */
/* ================================================================== */

const DEALS_KEY = "/api/v1/deals/?limit=50";

export default function RenovationPage() {
  const [renovations, setRenovations] = useState<Renovation[]>([]);
  const [selectedRenoId, setSelectedRenoId] = useState<string | null>(null);
  const [renovLoading, setRenovLoading] = useState(false);
  const [expenseFormOpen, setExpenseFormOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [createMsg, setCreateMsg] = useState("");

  const { data: dealsData, isLoading: dealsLoading } = useSWR<{ items: Deal[] } | null>(DEALS_KEY);
  const deals = dealsData?.items ?? [];

  /* --- Load renovations once deals list is available --- */
  useEffect(() => {
    if (deals.length === 0) {
      setRenovations([]);
      return;
    }
    let cancelled = false;
    (async () => {
      setRenovLoading(true);
      const renos: Renovation[] = [];
      for (const deal of deals.slice(0, 20)) {
        if (cancelled) return;
        const ren = await apiGet<RenovationDetail | Renovation | Renovation[]>(
          `/api/v1/renovations/deals/${deal.id}`
        );
        if (!ren) continue;
        if (Array.isArray(ren)) {
          for (const r of ren) {
            renos.push({ ...r, deal_title: deal.title ?? "?" });
          }
        } else if ("renovation" in ren && ren.renovation) {
          renos.push({ ...ren.renovation, deal_title: deal.title ?? "?" });
        } else if ("id" in ren) {
          renos.push({ ...(ren as Renovation), deal_title: deal.title ?? "?" });
        }
      }
      if (!cancelled) {
        setRenovations(renos);
        setRenovLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [deals]);

  const loading = dealsLoading || renovLoading;

  /* --- Detail via SWR --- */
  const selectedReno = renovations.find((r) => r.id === selectedRenoId);
  const detailKey = selectedReno ? `/api/v1/renovations/deals/${selectedReno.deal_id}` : null;
  const expensesKey = selectedRenoId ? `/api/v1/renovations/${selectedRenoId}/expenses` : null;

  const { data: detail } = useSWR<RenovationDetail | null>(detailKey);
  const { data: expensesData } = useSWR<Expense[] | null>(expensesKey);
  const expenses = Array.isArray(expensesData) ? expensesData : [];

  const refreshDetail = () => {
    if (detailKey) globalMutate(detailKey);
    if (expensesKey) globalMutate(expensesKey);
  };

  /* --- Create renovation --- */
  async function handleCreateRenovation(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setCreateMsg("");
    const fd = new FormData(e.currentTarget);
    const dealId = fd.get("r_deal_id") as string;
    if (!dealId) {
      setCreateMsg("Erro: seleccione um deal.");
      return;
    }
    const body = {
      initial_budget: Number(fd.get("r_budget") || 0),
      contractor_name: (fd.get("r_contractor") as string) || null,
      scope_description: (fd.get("r_scope") as string) || null,
      license_type: (fd.get("r_license") as string) || "isento",
      contingency_pct: Number(fd.get("r_contingency") || 15),
      is_aru: fd.get("r_aru") === "on",
      auto_milestones: true,
    };
    if (!body.initial_budget || body.initial_budget <= 0) {
      setCreateMsg("Erro: orçamento inicial deve ser maior que 0.");
      return;
    }
    try {
      const result = await apiPost(`/api/v1/renovations/deals/${dealId}/create`, body);
      if (result) {
        setCreateMsg("Obra criada!");
        (e.target as HTMLFormElement).reset();
        setCreateOpen(false);
        globalMutate(DEALS_KEY);
      } else {
        setCreateMsg("Erro ao criar obra.");
      }
    } catch {
      setCreateMsg("Erro de comunicação.");
    }
  }

  /* --- Milestone actions --- */
  async function handleStartMilestone(milestoneId: string) {
    await apiPost(`/api/v1/renovations/milestones/${milestoneId}/start`);
    refreshDetail();
  }

  async function handleCompleteMilestone(milestoneId: string) {
    await apiPost(`/api/v1/renovations/milestones/${milestoneId}/complete`);
    refreshDetail();
  }

  /* --- Add expense --- */
  async function handleAddExpense(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selectedRenoId) return;
    const fd = new FormData(e.currentTarget);
    const today = new Date().toISOString().split("T")[0];

    await apiPost(`/api/v1/renovations/${selectedRenoId}/expenses`, {
      description: fd.get("exp_desc"),
      amount: Number(fd.get("exp_amount") || 0),
      expense_date: `${today}T00:00:00`,
      category: fd.get("exp_category"),
      payment_method: fd.get("exp_payment"),
      has_valid_invoice: fd.get("exp_invoice") === "on",
    });

    e.currentTarget.reset();
    setExpenseFormOpen(false);
    refreshDetail();
  }

  /* ---------------------------------------------------------------- */
  /*  Computed                                                         */
  /* ---------------------------------------------------------------- */

  const totalBudget = renovations.reduce((s, r) => s + (r.initial_budget || 0), 0);
  const totalSpent = renovations.reduce((s, r) => s + (r.total_spent || 0), 0);
  const avgProgress =
    renovations.length > 0
      ? renovations.reduce((s, r) => s + (r.progress_pct || 0), 0) / renovations.length
      : 0;

  const reno = detail?.renovation;
  const milestones = detail?.milestones ?? [];
  const expSummary = detail?.expense_summary;
  const budget = reno?.current_budget ?? reno?.initial_budget ?? 0;
  const spent = reno?.total_spent ?? 0;

  /* ---------------------------------------------------------------- */
  /*  Render                                                           */
  /* ---------------------------------------------------------------- */

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">M6 — Gestão de Obra</h1>
          <p className="text-sm text-slate-500 mt-1">
            Orçamento, milestones, despesas e progresso
          </p>
        </div>
        <button
          onClick={() => setCreateOpen((v) => !v)}
          className="px-4 py-2 bg-teal-700 text-white rounded-lg text-sm font-medium hover:bg-teal-800 transition-colors"
        >
          {createOpen ? "Fechar" : "Criar obra"}
        </button>
      </div>

      {/* Create renovation form */}
      {createOpen && (
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <p className="text-sm font-semibold text-slate-700 mb-3">Nova obra</p>
          {createMsg && (
            <div className={`mb-3 px-3 py-2 rounded-lg text-sm ${createMsg.includes("Erro") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
              {createMsg}
            </div>
          )}
          <form onSubmit={handleCreateRenovation} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="block text-xs font-medium text-slate-600 mb-1">Deal *</label>
                <select name="r_deal_id" required className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-teal-500">
                  <option value="">Seleccionar deal...</option>
                  {deals.map((d) => (
                    <option key={d.id} value={d.id}>{d.title ?? d.id} ({d.status ?? "?"})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Orçamento inicial (EUR) *</label>
                <input name="r_budget" type="number" step="any" required placeholder="60000" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Contingência (%)</label>
                <input name="r_contingency" type="number" step="any" defaultValue="15" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Empreiteiro</label>
                <input name="r_contractor" type="text" placeholder="Nome do empreiteiro" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Tipo de licença</label>
                <select name="r_license" defaultValue="isento" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-teal-500">
                  <option value="isento">Isento</option>
                  <option value="comunicacao_previa">Comunicação prévia</option>
                  <option value="licenciamento">Licenciamento</option>
                </select>
              </div>
              <div className="col-span-2">
                <label className="block text-xs font-medium text-slate-600 mb-1">Âmbito da obra</label>
                <textarea name="r_scope" rows={2} placeholder="Descrição do que vai ser feito..." className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
              </div>
              <div className="col-span-2 flex items-center gap-2">
                <input name="r_aru" type="checkbox" id="r_aru" className="w-4 h-4" />
                <label htmlFor="r_aru" className="text-xs text-slate-600">Imóvel em zona ARU (reabilitação urbana)</label>
              </div>
            </div>
            <button type="submit" className="px-4 py-2 bg-teal-700 text-white rounded-lg text-sm font-medium hover:bg-teal-800 transition-colors">
              Criar obra
            </button>
          </form>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
          <p className="text-sm text-slate-500">A carregar obras...</p>
        </div>
      )}

      {/* No renovations */}
      {!loading && renovations.length === 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
          <h3 className="text-lg font-semibold text-slate-600">Sem obras activas</h3>
          <p className="text-sm text-slate-400 mt-1">
            Crie uma renovação a partir do detalhe de um deal no M4.
          </p>
        </div>
      )}

      {/* Summary KPIs */}
      {!loading && renovations.length > 0 && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <p className="text-xs text-slate-500">Obras activas</p>
              <p className="text-xl font-bold text-slate-900 mt-1">{renovations.length}</p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <p className="text-xs text-slate-500">Orçamento total</p>
              <p className="text-xl font-bold text-slate-900 mt-1">{formatEUR(totalBudget)}</p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <p className="text-xs text-slate-500">Total gasto</p>
              <p className="text-xl font-bold text-slate-900 mt-1">{formatEUR(totalSpent)}</p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <p className="text-xs text-slate-500">Progresso médio</p>
              <p className="text-xl font-bold text-slate-900 mt-1">{avgProgress.toFixed(0)}%</p>
            </div>
          </div>

          {/* Renovation cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {renovations.map((ren) => {
              const renBudget = ren.initial_budget || 0;
              const renSpent = ren.total_spent || 0;
              const renProgress = ren.progress_pct || 0;
              const variance = ren.budget_variance_pct || 0;

              return (
                <button
                  key={ren.id}
                  onClick={() => setSelectedRenoId(ren.id)}
                  className={`text-left bg-white rounded-xl border p-5 transition-colors ${
                    selectedRenoId === ren.id
                      ? "border-teal-700 ring-1 ring-teal-700"
                      : "border-slate-200 hover:border-slate-300"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-semibold text-slate-900 truncate">
                      {ren.deal_title}
                    </h3>
                    <span className="text-xs bg-slate-100 px-2 py-0.5 rounded text-slate-600">
                      {ren.status}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-slate-500 mb-3">
                    <span>{formatEUR(renSpent)} / {formatEUR(renBudget)}</span>
                    {variance !== 0 && (
                      <span className={variance > 0 ? "text-red-500" : "text-green-500"}>
                        {variance > 0 ? "+" : ""}{variance.toFixed(1)}%
                      </span>
                    )}
                  </div>
                  {/* Progress bar */}
                  <div className="w-full bg-slate-200 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full transition-all ${
                        renProgress >= 100
                          ? "bg-green-500"
                          : variance > 10
                          ? "bg-amber-500"
                          : "bg-teal-700"
                      }`}
                      style={{ width: `${Math.min(renProgress, 100)}%` }}
                    />
                  </div>
                  <p className="text-xs text-slate-500 mt-1.5 text-right">
                    {renProgress.toFixed(0)}%
                  </p>
                  {ren.contractor_name && (
                    <p className="text-xs text-slate-400 mt-1">
                      Empreiteiro: {ren.contractor_name}
                    </p>
                  )}
                </button>
              );
            })}
          </div>
        </>
      )}

      {/* ============================================================ */}
      {/*  Detail panel                                                 */}
      {/* ============================================================ */}
      {selectedRenoId && reno && (
        <div className="space-y-6">
          <hr className="border-slate-200" />

          {/* Detail KPIs */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <p className="text-xs text-slate-500">Orçamento</p>
              <p className="text-xl font-bold text-slate-900 mt-1">{formatEUR(budget)}</p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <p className="text-xs text-slate-500">Gasto</p>
              <p className="text-xl font-bold text-slate-900 mt-1">{formatEUR(spent)}</p>
              {reno.budget_variance_pct !== 0 && (
                <p
                  className={`text-xs mt-0.5 ${
                    reno.budget_variance_pct > 0 ? "text-red-500" : "text-green-500"
                  }`}
                >
                  {reno.budget_variance_pct > 0 ? "+" : ""}
                  {reno.budget_variance_pct.toFixed(1)}%
                </p>
              )}
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <p className="text-xs text-slate-500">Restante</p>
              <p className="text-xl font-bold text-slate-900 mt-1">
                {formatEUR(budget - spent)}
              </p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <p className="text-xs text-slate-500">Progresso</p>
              <p className="text-xl font-bold text-slate-900 mt-1">
                {(reno.progress_pct || 0).toFixed(0)}%
              </p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <p className="text-xs text-slate-500">Empreiteiro</p>
              <p className="text-sm font-medium text-slate-900 mt-1">
                {reno.contractor_name || "N/D"}
              </p>
            </div>
          </div>

          {/* Progress bar */}
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <div className="w-full bg-slate-200 rounded-full h-3">
              <div
                className="bg-teal-700 h-3 rounded-full transition-all"
                style={{ width: `${Math.min(reno.progress_pct || 0, 100)}%` }}
              />
            </div>
          </div>

          {/* Scope */}
          {reno.scope_description && (
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <p className="text-xs text-slate-500 mb-1">Âmbito</p>
              <p className="text-sm text-slate-700">{reno.scope_description}</p>
            </div>
          )}

          {/* ====== Milestones ====== */}
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h2 className="text-lg font-semibold mb-4">Milestones</h2>
            {milestones.length === 0 ? (
              <p className="text-sm text-slate-500">Sem milestones.</p>
            ) : (
              <div className="space-y-3">
                {milestones.map((m) => (
                  <div
                    key={m.id}
                    className="border border-slate-100 rounded-lg p-4"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-3">
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-medium ${
                            MILESTONE_STATUS_COLORS[m.status] ??
                            MILESTONE_STATUS_COLORS.pendente
                          }`}
                        >
                          {MILESTONE_STATUS_ICONS[m.status] ?? "?"} {m.status}
                        </span>
                        <span className="text-sm font-medium text-slate-900">
                          {m.name}
                        </span>
                      </div>
                      <span className="text-xs text-slate-500">
                        {formatEUR(m.spent)} / {formatEUR(m.budget)} ({m.completion_pct}%)
                      </span>
                    </div>

                    {/* Milestone progress */}
                    <div className="w-full bg-slate-200 rounded-full h-1.5 mb-2">
                      <div
                        className="bg-teal-600 h-1.5 rounded-full transition-all"
                        style={{ width: `${Math.min(m.completion_pct, 100)}%` }}
                      />
                    </div>

                    {m.description && (
                      <p className="text-xs text-slate-500 mb-2">{m.description}</p>
                    )}
                    {m.supplier_name && (
                      <p className="text-xs text-slate-400 mb-2">
                        Fornecedor: {m.supplier_name}
                      </p>
                    )}

                    {/* Actions */}
                    <div className="flex gap-2 mt-2">
                      {m.status === "pendente" && (
                        <button
                          onClick={() => handleStartMilestone(m.id)}
                          className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700 transition-colors"
                        >
                          Iniciar
                        </button>
                      )}
                      {m.status === "em_curso" && (
                        <button
                          onClick={() => handleCompleteMilestone(m.id)}
                          className="text-xs bg-green-600 text-white px-3 py-1.5 rounded-lg hover:bg-green-700 transition-colors"
                        >
                          Concluir
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ====== Financial summary ====== */}
          {expSummary && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <p className="text-xs text-slate-500">Total gasto</p>
                <p className="text-xl font-bold text-slate-900 mt-1">
                  {formatEUR(expSummary.total_spent ?? 0)}
                </p>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <p className="text-xs text-slate-500">Dedutível</p>
                <p className="text-xl font-bold text-green-700 mt-1">
                  {formatEUR(expSummary.total_deductible ?? 0)}
                </p>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <p className="text-xs text-slate-500">Não dedutível</p>
                <p className="text-xl font-bold text-amber-600 mt-1">
                  {formatEUR(expSummary.total_non_deductible ?? 0)}
                </p>
              </div>
            </div>
          )}

          {/* ====== Expenses ====== */}
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Despesas</h2>
              <button
                onClick={() => setExpenseFormOpen(!expenseFormOpen)}
                className="text-sm bg-teal-700 text-white px-4 py-2 rounded-lg hover:bg-teal-800 transition-colors"
              >
                {expenseFormOpen ? "Fechar" : "Nova despesa"}
              </button>
            </div>

            {/* Add expense form */}
            {expenseFormOpen && (
              <form
                onSubmit={handleAddExpense}
                className="border border-slate-200 rounded-lg p-4 mb-4 space-y-4"
              >
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      Descrição
                    </label>
                    <input
                      name="exp_desc"
                      required
                      placeholder="Material de construção"
                      className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-500 focus:border-teal-500 outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      Valor (EUR)
                    </label>
                    <input
                      name="exp_amount"
                      type="number"
                      required
                      min="0"
                      step="0.01"
                      placeholder="1500"
                      className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-500 focus:border-teal-500 outline-none"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      Categoria
                    </label>
                    <select
                      name="exp_category"
                      className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white focus:ring-2 focus:ring-teal-500 focus:border-teal-500 outline-none"
                    >
                      {EXPENSE_CATEGORIES.map((c) => (
                        <option key={c.value} value={c.value}>
                          {c.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      Método pagamento
                    </label>
                    <select
                      name="exp_payment"
                      className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white focus:ring-2 focus:ring-teal-500 focus:border-teal-500 outline-none"
                    >
                      {PAYMENT_METHODS.map((p) => (
                        <option key={p.value} value={p.value}>
                          {p.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex items-end">
                    <label className="flex items-center gap-2 text-sm text-slate-700">
                      <input
                        name="exp_invoice"
                        type="checkbox"
                        className="rounded border-slate-300 text-teal-700 focus:ring-teal-500"
                      />
                      Factura válida com NIF
                    </label>
                  </div>
                </div>
                <button
                  type="submit"
                  className="bg-teal-700 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-teal-800 transition-colors"
                >
                  Registar despesa
                </button>
              </form>
            )}

            {/* Expenses table */}
            {expenses.length === 0 ? (
              <p className="text-sm text-slate-500">Sem despesas registadas.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-slate-600">
                    <tr>
                      <th className="text-left px-4 py-3 font-medium">Descrição</th>
                      <th className="text-right px-4 py-3 font-medium">Valor</th>
                      <th className="text-left px-4 py-3 font-medium">Categoria</th>
                      <th className="text-left px-4 py-3 font-medium">Pagamento</th>
                      <th className="text-center px-4 py-3 font-medium">Factura</th>
                      <th className="text-left px-4 py-3 font-medium">Data</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {expenses.map((exp) => (
                      <tr key={exp.id} className="hover:bg-slate-50">
                        <td className="px-4 py-3 text-slate-900">{exp.description}</td>
                        <td className="px-4 py-3 text-right font-medium">
                          {formatEUR(exp.amount)}
                        </td>
                        <td className="px-4 py-3">
                          <span className="inline-block px-2 py-0.5 rounded text-xs bg-slate-100 text-slate-600">
                            {exp.category}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-slate-600">
                          {exp.payment_method ?? "—"}
                        </td>
                        <td className="px-4 py-3 text-center">
                          {exp.has_valid_invoice ? (
                            <span className="text-green-600 font-medium">Sim</span>
                          ) : (
                            <span className="text-slate-400">Não</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-slate-500 text-xs">
                          {exp.expense_date
                            ? exp.expense_date.slice(0, 10)
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
