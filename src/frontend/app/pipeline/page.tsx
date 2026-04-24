"use client";

import { useState } from "react";
import useSWR, { mutate as globalMutate } from "swr";
import { formatEUR } from "@/lib/utils";
import { apiPost, apiPatch } from "@/lib/api";

interface Deal {
  id: string;
  title: string;
  property_id?: string;
  investment_strategy?: string;
  strategy?: string;
  strategy_icon?: string;
  strategy_label?: string;
  status?: string;
  status_label?: string;
  status_icon?: string;
  current_state?: string;
  purchase_price?: number;
  target_sale_price?: number;
  asking_price?: number;
  monthly_rent?: number;
  renovation_budget?: number;
  offered_price?: number;
  estimated_arv?: number;
  progress_pct?: number;
  days_in_status?: number;
  contact_name?: string;
  contact_phone?: string;
  notes?: string;
  created_at?: string;
  property?: Record<string, any>;
  properties?: Record<string, any>;
}

interface KanbanData {
  columns: Record<string, Deal[]>;
  total_deals: number;
  status_config: Record<string, { label: string; color: string; icon: string }>;
}

interface DealStats {
  active_deals: number;
  completed_deals: number;
  discarded_deals: number;
  total_invested?: number;
  total_monthly_rent?: number;
  by_strategy?: Record<string, number>;
  by_status?: Record<string, { count: number; value: number }>;
}

interface Strategy {
  key: string;
  label: string;
  icon?: string;
  description?: string;
  role?: string;
}

interface Proposal {
  id: string;
  proposal_type: string;
  amount: number;
  deposit_pct: number;
  status: string;
  conditions?: string;
  created_at?: string;
}

interface HistoryEntry {
  from_status?: string;
  to_status?: string;
  reason?: string;
  created_at?: string;
}

interface NextAction {
  status: string;
  label: string;
  icon?: string;
}

type PipelineTab = "kanban" | "create" | "mediation";
type DetailTab = "resumo" | "propostas" | "visitas" | "tasks" | "hist";

interface DealTask {
  id: string;
  deal_id?: string;
  title: string;
  description?: string;
  task_type?: string;
  priority?: string;
  due_date?: string;
  assigned_to?: string;
  is_completed?: boolean;
  completed_at?: string;
  created_at?: string;
}

interface Visit {
  id: string;
  visitor_name: string;
  visitor_phone?: string;
  visitor_email?: string;
  visit_date?: string;
  visit_type?: string;
  duration_minutes?: number;
  accompanied_by?: string;
  interest_level?: string;
  feedback?: string;
  wants_second_visit?: boolean;
  made_proposal?: boolean;
  created_at?: string;
}

/* ------------------------------------------------------------------ */
/*  Status config for kanban columns (used when reading from Supabase) */
/* ------------------------------------------------------------------ */
const DEFAULT_STATUS_CONFIG: Record<string, { label: string; color: string; icon: string }> = {
  triagem: { label: "Triagem", color: "#94A3B8", icon: "" },
  analise: { label: "Análise", color: "#2563EB", icon: "" },
  proposta: { label: "Proposta", color: "#7C3AED", icon: "" },
  negociacao: { label: "Negociação", color: "#D97706", icon: "" },
  cpcv: { label: "CPCV", color: "#14B8A6", icon: "" },
  escritura: { label: "Escritura", color: "#0F766E", icon: "" },
  obra: { label: "Obra", color: "#F59E0B", icon: "" },
  venda: { label: "Venda", color: "#16A34A", icon: "" },
  concluido: { label: "Concluído", color: "#16A34A", icon: "" },
  descartado: { label: "Descartado", color: "#DC2626", icon: "" },
  em_pausa: { label: "Em Pausa", color: "#94A3B8", icon: "" },
  angariacao: { label: "Angariação", color: "#2563EB", icon: "" },
  preparacao: { label: "Preparação", color: "#7C3AED", icon: "" },
  marketing: { label: "Marketing", color: "#D97706", icon: "" },
  visitas: { label: "Visitas", color: "#14B8A6", icon: "" },
  fecho: { label: "Fecho", color: "#0F766E", icon: "" },
};

export default function PipelinePage() {
  const [activeTab, setActiveTab] = useState<PipelineTab>("kanban");
  const [strategyFilter, setStrategyFilter] = useState("");

  // Deal detail
  const [selectedDealId, setSelectedDealId] = useState<string | null>(null);
  const [detailTab, setDetailTab] = useState<DetailTab>("resumo");

  // Create deal
  const [createMsg, setCreateMsg] = useState("");
  const [createLoading, setCreateLoading] = useState(false);

  // Advance
  const [advanceLoading, setAdvanceLoading] = useState(false);
  const [advanceMsg, setAdvanceMsg] = useState("");
  const [pendingAction, setPendingAction] = useState<{ status: string; label: string } | null>(null);
  const [advanceReason, setAdvanceReason] = useState("");

  // Proposal creation
  const [proposalMsg, setProposalMsg] = useState("");

  // Visit creation
  const [visitMsg, setVisitMsg] = useState("");

  // Task creation
  const [taskMsg, setTaskMsg] = useState("");

  // SWR keys
  const kanbanKey = `/api/v1/deals/kanban${strategyFilter ? `?strategy=${strategyFilter}` : ""}`;
  const STATS_KEY = "/api/v1/deals/stats";
  const DEALS_KEY = "/api/v1/deals/?limit=100";
  const STRATEGIES_KEY = "/api/v1/deals/strategies";
  const PROPERTIES_KEY = "/api/v1/properties/?limit=100";
  const MED_KANBAN_KEY = "/api/v1/deals/kanban?strategy=mediacao_venda";
  const MED_STATS_KEY = "/api/v1/deals/stats/mediation";

  const { data: kanban, isLoading: kanbanLoading } = useSWR<KanbanData | null>(kanbanKey);
  const { data: stats } = useSWR<DealStats | null>(STATS_KEY);
  const { data: dealsResp } = useSWR<{ items: Deal[] } | null>(DEALS_KEY);
  const { data: strategiesData } = useSWR<Strategy[] | null>(STRATEGIES_KEY);
  const dealsList = dealsResp?.items ?? [];
  const strategies = strategiesData ?? [];
  const loading = kanbanLoading;

  const { data: propsResp } = useSWR<{ items: any[] } | null>(
    activeTab === "create" ? PROPERTIES_KEY : null
  );
  const properties = (propsResp?.items ?? []).map((p: any) => ({
    id: p.id,
    label: `${p.municipality ?? "?"} — ${p.typology ?? "?"} (${formatEUR(p.asking_price)})`,
  }));

  const { data: medKanban } = useSWR<KanbanData | null>(
    activeTab === "mediation" ? MED_KANBAN_KEY : null
  );
  const { data: medStats } = useSWR<Record<string, any> | null>(
    activeTab === "mediation" ? MED_STATS_KEY : null
  );

  const dealDetailKey = selectedDealId ? `/api/v1/deals/${selectedDealId}` : null;
  const proposalsKey = selectedDealId ? `/api/v1/deals/${selectedDealId}/proposals` : null;
  const visitsKey = selectedDealId ? `/api/v1/deals/${selectedDealId}/visits` : null;
  const tasksKey = selectedDealId ? `/api/v1/deals/${selectedDealId}/tasks` : null;
  const historyKey = selectedDealId ? `/api/v1/deals/${selectedDealId}/history` : null;
  const nextActionsKey = selectedDealId ? `/api/v1/deals/${selectedDealId}/next-actions` : null;

  const { data: selectedDeal } = useSWR<Deal | null>(dealDetailKey);
  const { data: proposalsData } = useSWR<Proposal[] | null>(proposalsKey);
  const { data: visitsData } = useSWR<Visit[] | null>(visitsKey);
  const { data: tasksData } = useSWR<DealTask[] | null>(tasksKey);
  const { data: historyData } = useSWR<HistoryEntry[] | null>(historyKey);
  const { data: nextActionsData } = useSWR<{ next_statuses: NextAction[] } | null>(nextActionsKey);
  const proposals = proposalsData ?? [];
  const visits = visitsData ?? [];
  const tasks = tasksData ?? [];
  const history = historyData ?? [];
  const nextActions = nextActionsData?.next_statuses ?? [];

  const refreshPipeline = async () => {
    await Promise.all([
      globalMutate(kanbanKey),
      globalMutate(STATS_KEY),
      globalMutate(DEALS_KEY),
    ]);
  };

  // Write operations: always via FastAPI (needs business logic)
  async function handleCreateDeal(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setCreateLoading(true);
    setCreateMsg("");
    const fd = new FormData(e.currentTarget);
    const body: Record<string, any> = {
      property_id: fd.get("property_id"),
      investment_strategy: fd.get("strategy"),
      title: fd.get("title"),
    };
    if (fd.get("purchase_price")) body.purchase_price = Number(fd.get("purchase_price"));
    if (fd.get("target_sale_price")) body.target_sale_price = Number(fd.get("target_sale_price"));
    if (fd.get("monthly_rent")) body.monthly_rent = Number(fd.get("monthly_rent"));
    if (fd.get("renovation_budget")) body.renovation_budget = Number(fd.get("renovation_budget"));

    try {
      const data = await apiPost<Deal>("/api/v1/deals/", body);
      if (data) {
        setCreateMsg(`Deal criado: ${data.title ?? data.id}`);
        (e.target as HTMLFormElement).reset();
        await refreshPipeline();
      } else {
        setCreateMsg("Erro ao criar deal.");
      }
    } catch {
      setCreateMsg("Erro de comunicação.");
    } finally {
      setCreateLoading(false);
    }
  }

  async function handleAdvance(targetStatus: string, reason?: string) {
    if (!selectedDealId) return;
    setAdvanceLoading(true);
    setAdvanceMsg("");
    try {
      const result = await apiPost(`/api/v1/deals/${selectedDealId}/advance`, { target_status: targetStatus, reason: reason || null });
      if (result) {
        setAdvanceMsg(`Avançado para ${targetStatus}`);
        setPendingAction(null);
        setAdvanceReason("");
        await refreshPipeline();
        if (dealDetailKey) globalMutate(dealDetailKey);
        if (historyKey) globalMutate(historyKey);
        if (nextActionsKey) globalMutate(nextActionsKey);
      } else {
        setAdvanceMsg("Erro ao avançar deal.");
      }
    } catch {
      setAdvanceMsg("Erro de comunicação.");
    } finally {
      setAdvanceLoading(false);
    }
  }

  async function handleCreateProposal(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selectedDealId) return;
    setProposalMsg("");
    const fd = new FormData(e.currentTarget);
    const body = {
      proposal_type: fd.get("p_type") as string,
      amount: Number(fd.get("p_amount")),
      deposit_pct: Number(fd.get("p_deposit")) || 10,
      conditions: (fd.get("p_conditions") as string) || null,
    };
    try {
      const result = await apiPost(`/api/v1/deals/${selectedDealId}/proposals`, body);
      if (result) {
        setProposalMsg("Proposta criada!");
        (e.target as HTMLFormElement).reset();
        if (proposalsKey) globalMutate(proposalsKey);
      } else {
        setProposalMsg("Erro ao criar proposta.");
      }
    } catch {
      setProposalMsg("Erro de comunicação.");
    }
  }

  async function handleCreateTask(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selectedDealId) return;
    setTaskMsg("");
    const fd = new FormData(e.currentTarget);
    const title = ((fd.get("t_title") as string) || "").trim();
    if (!title) {
      setTaskMsg("Erro: título é obrigatório.");
      return;
    }
    const dueRaw = (fd.get("t_due") as string) || "";
    const body: Record<string, unknown> = {
      title,
      description: ((fd.get("t_desc") as string) || "").trim() || null,
      priority: (fd.get("t_priority") as string) || "medium",
      due_date: dueRaw ? new Date(dueRaw).toISOString() : null,
      assigned_to: ((fd.get("t_assignee") as string) || "").trim() || null,
    };
    try {
      const result = await apiPost(`/api/v1/deals/${selectedDealId}/tasks`, body);
      if (result) {
        setTaskMsg("Tarefa criada!");
        (e.target as HTMLFormElement).reset();
        if (tasksKey) globalMutate(tasksKey);
      } else {
        setTaskMsg("Erro ao criar tarefa.");
      }
    } catch {
      setTaskMsg("Erro de comunicação.");
    }
  }

  async function handleCompleteTask(taskId: string) {
    setTaskMsg("");
    try {
      const result = await apiPatch(`/api/v1/deals/tasks/${taskId}/complete`, {});
      if (result) {
        setTaskMsg("Tarefa concluída.");
        if (tasksKey) globalMutate(tasksKey);
      } else {
        setTaskMsg("Erro ao concluir tarefa.");
      }
    } catch {
      setTaskMsg("Erro de comunicação.");
    }
  }

  async function handleCreateVisit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selectedDealId) return;
    setVisitMsg("");
    const fd = new FormData(e.currentTarget);
    const dateRaw = (fd.get("v_date") as string) || "";
    const body: Record<string, unknown> = {
      visitor_name: (fd.get("v_name") as string) || "",
      visitor_phone: (fd.get("v_phone") as string) || null,
      visitor_email: (fd.get("v_email") as string) || null,
      visit_date: dateRaw ? new Date(dateRaw).toISOString() : new Date().toISOString(),
      visit_type: (fd.get("v_type") as string) || "presencial",
      duration_minutes: Number(fd.get("v_duration")) || null,
      accompanied_by: (fd.get("v_by") as string) || null,
    };
    if (!body.visitor_name) {
      setVisitMsg("Erro: nome do visitante é obrigatório.");
      return;
    }
    try {
      const result = await apiPost(`/api/v1/deals/${selectedDealId}/visits`, body);
      if (result) {
        setVisitMsg("Visita registada!");
        (e.target as HTMLFormElement).reset();
        if (visitsKey) globalMutate(visitsKey);
      } else {
        setVisitMsg("Erro ao registar visita.");
      }
    } catch {
      setVisitMsg("Erro de comunicação.");
    }
  }

  const columns = kanban?.columns ?? {};
  const statusConfig = kanban?.status_config ?? {};
  const colEntries = Object.entries(columns);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">M4 — Deal Pipeline</h1>
        <p className="text-sm text-slate-500 mt-1">{kanban?.total_deals ?? 0} deals no pipeline</p>
      </div>

      {/* Stats KPIs */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <StatCard label="Deals ativos" value={String(stats.active_deals ?? 0)} />
          <StatCard label="Concluídos" value={String(stats.completed_deals ?? 0)} />
          <StatCard label="Descartados" value={String(stats.discarded_deals ?? 0)} />
          <StatCard label="Valor investido" value={formatEUR(stats.total_invested)} />
          <StatCard label="Renda mensal" value={formatEUR(stats.total_monthly_rent)} />
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-100 rounded-lg p-1 w-fit">
        {([
          ["kanban", "Kanban"],
          ["create", "Criar Deal"],
          ["mediation", "Mediação"],
        ] as [PipelineTab, string][]).map(([key, label]) => (
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

      {/* ===== KANBAN TAB ===== */}
      {activeTab === "kanban" && (
        <>
          {/* Strategy filter */}
          <div>
            <select
              value={strategyFilter}
              onChange={(e) => setStrategyFilter(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-teal-500"
            >
              <option value="">Todas as estratégias</option>
              {strategies.map((s) => (
                <option key={s.key} value={s.key}>{s.icon ?? ""} {s.label}</option>
              ))}
            </select>
          </div>

          {/* Kanban board */}
          {loading ? (
            <div className="text-center py-16 text-slate-400">A carregar...</div>
          ) : colEntries.length > 0 ? (
            <div className="flex gap-4 overflow-x-auto pb-4">
              {colEntries.map(([state, deals]) => {
                const cfg = statusConfig[state] ?? { label: state, color: "#94A3B8", icon: "" };
                const colValue = deals.reduce((sum: number, d: Deal) => sum + ((d as any).purchase_price ?? 0), 0);
                return (
                  <div key={state} className="min-w-[280px] bg-slate-50 rounded-xl p-3 flex-shrink-0">
                    {/* Column header */}
                    <div
                      className="text-center py-2 px-3 rounded-lg mb-3"
                      style={{
                        backgroundColor: `${cfg.color}15`,
                        borderBottom: `3px solid ${cfg.color}`,
                      }}
                    >
                      <p className="text-sm font-bold text-slate-700">{cfg.icon} {cfg.label}</p>
                      <p className="text-xs text-slate-500">
                        {deals.length} deal(s)
                        {colValue > 0 && ` — ${formatEUR(colValue)}`}
                      </p>
                    </div>

                    {/* Deal cards */}
                    <div className="space-y-2">
                      {deals.map((deal: Deal) => {
                        const days = (deal as any).days_in_status ?? 0;
                        const borderColor = days > 14 ? "#DC2626" : days > 7 ? "#D97706" : "#E2E8F0";
                        const daysColor = days > 14 ? "#DC2626" : days > 7 ? "#D97706" : "#64748B";
                        const progress = (deal as any).progress_pct ?? 0;
                        const price = deal.purchase_price ?? deal.asking_price;
                        return (
                          <div
                            key={deal.id}
                            onClick={() => setSelectedDealId(deal.id)}
                            className="bg-white rounded-lg p-3 border shadow-sm cursor-pointer hover:shadow-md transition-shadow"
                            style={{
                              borderColor,
                              borderLeftWidth: 4,
                              borderLeftColor: cfg.color,
                            }}
                          >
                            <p className="text-sm font-semibold text-slate-900">
                              {(deal as any).strategy_icon ?? ""} {deal.title || deal.property?.municipality || (deal.properties as any)?.municipality || "Sem título"}
                            </p>
                            <div className="flex items-center justify-between mt-1.5">
                              <span className="text-xs text-slate-500">{formatEUR(price)}</span>
                              <span className="text-xs" style={{ color: daysColor }}>{days}d</span>
                            </div>
                            {/* Progress bar */}
                            <div className="mt-2 h-1 bg-slate-200 rounded-full overflow-hidden">
                              <div
                                className="h-full rounded-full transition-all"
                                style={{ width: `${progress}%`, backgroundColor: cfg.color }}
                              />
                            </div>
                          </div>
                        );
                      })}
                      {deals.length === 0 && (
                        <p className="text-xs text-slate-400 text-center py-4">Sem deals</p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-center py-16 text-slate-400">
              <p className="text-lg">Pipeline vazio</p>
              <p className="text-sm mt-1">Use a tab &quot;Criar Deal&quot; para adicionar o primeiro deal</p>
            </div>
          )}

          {/* Deal detail */}
          {selectedDealId && selectedDeal && (
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-slate-900">
                  {(selectedDeal as any).strategy_icon ?? ""} {selectedDeal.title}
                </h2>
                <button
                  onClick={() => { setSelectedDealId(null); setPendingAction(null); setAdvanceMsg(""); }}
                  className="text-sm text-slate-400 hover:text-slate-600"
                >
                  Fechar
                </button>
              </div>

              {/* Deal selector */}
              <div className="mb-4">
                <select
                  value={selectedDealId}
                  onChange={(e) => setSelectedDealId(e.target.value)}
                  className="border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-teal-500 w-full max-w-md"
                >
                  {dealsList.map((d) => (
                    <option key={d.id} value={d.id}>
                      {(d as any).strategy_icon ?? ""} {d.title} ({(d as any).status_label ?? d.status})
                    </option>
                  ))}
                </select>
              </div>

              {/* Detail tabs */}
              <div className="flex gap-1 bg-slate-100 rounded-lg p-1 w-fit mb-4">
                {([
                  ["resumo", "Resumo"],
                  ["propostas", "Propostas"],
                  ["visitas", "Visitas"],
                  ["tasks", "Tasks"],
                  ["hist", "Histórico"],
                ] as [DetailTab, string][]).map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => setDetailTab(key)}
                    className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                      detailTab === key ? "bg-white text-teal-700 shadow-sm" : "text-slate-500 hover:text-slate-700"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {/* RESUMO TAB */}
              {detailTab === "resumo" && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2 text-sm">
                      <p><span className="text-slate-500">Estratégia:</span> {(selectedDeal as any).strategy_icon ?? ""} {(selectedDeal as any).strategy_label ?? selectedDeal.strategy}</p>
                      <p><span className="text-slate-500">Estado:</span> {(selectedDeal as any).status_icon ?? ""} {(selectedDeal as any).status_label ?? selectedDeal.status}</p>
                      <p><span className="text-slate-500">Progresso:</span> {((selectedDeal as any).progress_pct ?? 0).toFixed(0)}%</p>
                      {selectedDeal.purchase_price && <p><span className="text-slate-500">Compra:</span> {formatEUR(selectedDeal.purchase_price)}</p>}
                      {selectedDeal.target_sale_price && <p><span className="text-slate-500">Venda alvo:</span> {formatEUR(selectedDeal.target_sale_price)}</p>}
                      {selectedDeal.renovation_budget && <p><span className="text-slate-500">Orçamento obra:</span> {formatEUR(selectedDeal.renovation_budget)}</p>}
                    </div>
                    <div className="space-y-2 text-sm">
                      {selectedDeal.contact_name && <p><span className="text-slate-500">Contacto:</span> {selectedDeal.contact_name}</p>}
                      {selectedDeal.contact_phone && <p><span className="text-slate-500">Telefone:</span> {selectedDeal.contact_phone}</p>}
                      {selectedDeal.notes && <p><span className="text-slate-500">Notas:</span> {selectedDeal.notes}</p>}
                      {(selectedDeal as any).days_in_status != null && (
                        <p><span className="text-slate-500">Dias no estado:</span> {(selectedDeal as any).days_in_status}</p>
                      )}
                    </div>
                  </div>

                  {/* Progress bar */}
                  <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-teal-600 rounded-full transition-all"
                      style={{ width: `${(selectedDeal as any).progress_pct ?? 0}%` }}
                    />
                  </div>

                  {/* Actions */}
                  <div className="border-t border-slate-200 pt-4">
                    <p className="text-sm font-semibold text-slate-700 mb-3">Próximas ações</p>

                    {advanceMsg && (
                      <div className={`mb-3 px-3 py-2 rounded-lg text-sm ${advanceMsg.includes("Erro") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
                        {advanceMsg}
                      </div>
                    )}

                    {pendingAction ? (
                      <div className="space-y-3 bg-amber-50 rounded-lg p-4">
                        <p className="text-sm text-amber-700 font-medium">
                          Confirmar: {pendingAction.label}
                        </p>
                        <input
                          type="text"
                          placeholder="Motivo (opcional)"
                          value={advanceReason}
                          onChange={(e) => setAdvanceReason(e.target.value)}
                          className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500"
                        />
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleAdvance(pendingAction.status, advanceReason)}
                            disabled={advanceLoading}
                            className="px-4 py-2 bg-teal-700 text-white rounded-lg text-sm font-medium hover:bg-teal-800 disabled:opacity-50"
                          >
                            {advanceLoading ? "..." : "Confirmar"}
                          </button>
                          <button
                            onClick={() => { setPendingAction(null); setAdvanceReason(""); }}
                            className="px-4 py-2 bg-slate-200 text-slate-600 rounded-lg text-sm font-medium hover:bg-slate-300"
                          >
                            Cancelar
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-wrap gap-2">
                        {nextActions.map((action) => (
                          <button
                            key={action.status}
                            onClick={() => {
                              if (action.status === "descartado" || action.status === "em_pausa") {
                                setPendingAction({ status: action.status, label: action.label });
                              } else {
                                handleAdvance(action.status);
                              }
                            }}
                            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                              action.status === "descartado"
                                ? "bg-red-50 text-red-600 hover:bg-red-100"
                                : "bg-teal-50 text-teal-700 hover:bg-teal-100"
                            }`}
                          >
                            {action.icon ?? ""} {action.label}
                          </button>
                        ))}
                        {nextActions.length === 0 && (
                          <p className="text-xs text-slate-400">Sem ações disponíveis</p>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* PROPOSTAS TAB */}
              {detailTab === "propostas" && (
                <div className="space-y-4">
                  {proposals.length > 0 ? (
                    <div className="space-y-3">
                      {proposals.map((p) => (
                        <div key={p.id} className="border border-slate-200 rounded-lg p-3">
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-semibold text-slate-900">
                              {p.proposal_type.toUpperCase()} — {formatEUR(p.amount)}
                            </span>
                            <span className={`text-xs px-2 py-0.5 rounded ${
                              p.status === "accepted" ? "bg-green-100 text-green-700"
                              : p.status === "rejected" ? "bg-red-100 text-red-700"
                              : "bg-slate-100 text-slate-600"
                            }`}>
                              {p.status}
                            </span>
                          </div>
                          <p className="text-xs text-slate-500 mt-1">
                            Sinal: {p.deposit_pct}% | {p.created_at?.slice(0, 10) ?? ""}
                          </p>
                          {p.conditions && (
                            <p className="text-xs text-slate-400 mt-1">Condições: {p.conditions}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-slate-400">Sem propostas.</p>
                  )}

                  {/* New proposal form */}
                  <div className="border-t border-slate-200 pt-4">
                    <p className="text-sm font-semibold text-slate-700 mb-3">Nova proposta</p>
                    {proposalMsg && (
                      <div className={`mb-3 px-3 py-2 rounded-lg text-sm ${proposalMsg.includes("Erro") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
                        {proposalMsg}
                      </div>
                    )}
                    <form onSubmit={handleCreateProposal} className="space-y-3">
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="block text-xs font-medium text-slate-600 mb-1">Valor (EUR)</label>
                          <input name="p_amount" type="number" step="any" placeholder="250000" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 mb-1">Tipo</label>
                          <select name="p_type" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-teal-500">
                            <option value="offer">Offer</option>
                            <option value="counter">Counter</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 mb-1">Sinal (%)</label>
                          <input name="p_deposit" type="number" step="any" defaultValue="10" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 mb-1">Condições</label>
                          <input name="p_conditions" type="text" placeholder="Opcional" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
                        </div>
                      </div>
                      <button type="submit" className="px-4 py-2 bg-teal-700 text-white rounded-lg text-sm font-medium hover:bg-teal-800 transition-colors">
                        Enviar proposta
                      </button>
                    </form>
                  </div>
                </div>
              )}

              {/* VISITAS TAB */}
              {detailTab === "visitas" && (
                <div className="space-y-4">
                  {visits.length > 0 ? (
                    <div className="space-y-3">
                      {visits.map((v) => (
                        <div key={v.id} className="border border-slate-200 rounded-lg p-3">
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-semibold text-slate-900">
                              {v.visitor_name}
                              {v.visit_type && (
                                <span className="ml-2 text-xs px-2 py-0.5 bg-teal-50 text-teal-700 rounded">
                                  {v.visit_type}
                                </span>
                              )}
                            </span>
                            {v.interest_level && (
                              <span className="text-xs px-2 py-0.5 bg-slate-100 text-slate-600 rounded">
                                {v.interest_level}
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-slate-500 mt-1">
                            {v.visit_date?.slice(0, 16).replace("T", " ") ?? ""}
                            {v.duration_minutes ? ` · ${v.duration_minutes} min` : ""}
                            {v.accompanied_by ? ` · com ${v.accompanied_by}` : ""}
                          </p>
                          {(v.visitor_phone || v.visitor_email) && (
                            <p className="text-xs text-slate-400 mt-1">
                              {[v.visitor_phone, v.visitor_email].filter(Boolean).join(" · ")}
                            </p>
                          )}
                          {v.feedback && (
                            <p className="text-xs text-slate-500 mt-2 italic">&ldquo;{v.feedback}&rdquo;</p>
                          )}
                          {(v.wants_second_visit || v.made_proposal) && (
                            <div className="flex gap-2 mt-2">
                              {v.wants_second_visit && (
                                <span className="text-xs px-2 py-0.5 bg-amber-50 text-amber-700 rounded">2ª visita</span>
                              )}
                              {v.made_proposal && (
                                <span className="text-xs px-2 py-0.5 bg-green-50 text-green-700 rounded">propôs</span>
                              )}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-slate-400">Sem visitas registadas.</p>
                  )}

                  <div className="border-t border-slate-200 pt-4">
                    <p className="text-sm font-semibold text-slate-700 mb-3">Registar visita</p>
                    {visitMsg && (
                      <div className={`mb-3 px-3 py-2 rounded-lg text-sm ${visitMsg.includes("Erro") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
                        {visitMsg}
                      </div>
                    )}
                    <form onSubmit={handleCreateVisit} className="space-y-3">
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="block text-xs font-medium text-slate-600 mb-1">Nome *</label>
                          <input name="v_name" type="text" required placeholder="Ana Investidora" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 mb-1">Tipo</label>
                          <select name="v_type" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-teal-500">
                            <option value="presencial">Presencial</option>
                            <option value="virtual">Virtual</option>
                            <option value="open_house">Open House</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 mb-1">Data/hora</label>
                          <input name="v_date" type="datetime-local" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 mb-1">Duração (min)</label>
                          <input name="v_duration" type="number" step="1" defaultValue="45" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 mb-1">Telefone</label>
                          <input name="v_phone" type="tel" placeholder="+351 ..." className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 mb-1">Email</label>
                          <input name="v_email" type="email" placeholder="opcional" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
                        </div>
                        <div className="col-span-2">
                          <label className="block text-xs font-medium text-slate-600 mb-1">Acompanhado por</label>
                          <input name="v_by" type="text" placeholder="Opcional (ex: agente João)" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
                        </div>
                      </div>
                      <button type="submit" className="px-4 py-2 bg-teal-700 text-white rounded-lg text-sm font-medium hover:bg-teal-800 transition-colors">
                        Registar visita
                      </button>
                    </form>
                  </div>
                </div>
              )}

              {/* TASKS TAB */}
              {detailTab === "tasks" && (
                <div className="space-y-4">
                  {tasks.length > 0 ? (
                    <div className="space-y-2">
                      {tasks.map((t) => {
                        const priorityColor =
                          t.priority === "urgent" ? "bg-red-100 text-red-700"
                          : t.priority === "high" ? "bg-amber-100 text-amber-700"
                          : t.priority === "low" ? "bg-slate-100 text-slate-500"
                          : "bg-blue-50 text-blue-700";
                        const overdue =
                          !t.is_completed && t.due_date && new Date(t.due_date) < new Date();
                        return (
                          <div
                            key={t.id}
                            className={`border rounded-lg p-3 ${t.is_completed ? "bg-slate-50 border-slate-200" : "border-slate-200"}`}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className={`text-sm font-semibold ${t.is_completed ? "text-slate-400 line-through" : "text-slate-900"}`}>
                                    {t.title}
                                  </span>
                                  {t.priority && (
                                    <span className={`text-xs px-2 py-0.5 rounded ${priorityColor}`}>
                                      {t.priority}
                                    </span>
                                  )}
                                  {t.task_type === "auto" && (
                                    <span className="text-xs px-2 py-0.5 rounded bg-purple-50 text-purple-700">auto</span>
                                  )}
                                  {overdue && (
                                    <span className="text-xs px-2 py-0.5 rounded bg-red-100 text-red-700">atrasada</span>
                                  )}
                                </div>
                                {t.description && (
                                  <p className="text-xs text-slate-500 mt-1">{t.description}</p>
                                )}
                                <p className="text-xs text-slate-400 mt-1">
                                  {t.due_date ? `Prazo: ${t.due_date.slice(0, 16).replace("T", " ")}` : "Sem prazo"}
                                  {t.assigned_to ? ` · ${t.assigned_to}` : ""}
                                  {t.is_completed && t.completed_at ? ` · concluída ${t.completed_at.slice(0, 10)}` : ""}
                                </p>
                              </div>
                              {!t.is_completed && (
                                <button
                                  onClick={() => handleCompleteTask(t.id)}
                                  className="flex-shrink-0 px-3 py-1.5 bg-teal-700 text-white rounded-md text-xs font-medium hover:bg-teal-800 transition-colors"
                                >
                                  Concluir
                                </button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="text-sm text-slate-400">Sem tarefas.</p>
                  )}

                  <div className="border-t border-slate-200 pt-4">
                    <p className="text-sm font-semibold text-slate-700 mb-3">Nova tarefa</p>
                    {taskMsg && (
                      <div className={`mb-3 px-3 py-2 rounded-lg text-sm ${taskMsg.includes("Erro") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
                        {taskMsg}
                      </div>
                    )}
                    <form onSubmit={handleCreateTask} className="space-y-3">
                      <div className="grid grid-cols-2 gap-3">
                        <div className="col-span-2">
                          <label className="block text-xs font-medium text-slate-600 mb-1">Título *</label>
                          <input name="t_title" type="text" required placeholder="Ex: Confirmar escritura com notário" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
                        </div>
                        <div className="col-span-2">
                          <label className="block text-xs font-medium text-slate-600 mb-1">Descrição</label>
                          <input name="t_desc" type="text" placeholder="Opcional" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 mb-1">Prioridade</label>
                          <select name="t_priority" defaultValue="medium" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-teal-500">
                            <option value="low">Low</option>
                            <option value="medium">Medium</option>
                            <option value="high">High</option>
                            <option value="urgent">Urgent</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 mb-1">Prazo</label>
                          <input name="t_due" type="datetime-local" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
                        </div>
                        <div className="col-span-2">
                          <label className="block text-xs font-medium text-slate-600 mb-1">Atribuída a</label>
                          <input name="t_assignee" type="text" placeholder="Opcional (ex: joão@exemplo.com)" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
                        </div>
                      </div>
                      <button type="submit" className="px-4 py-2 bg-teal-700 text-white rounded-lg text-sm font-medium hover:bg-teal-800 transition-colors">
                        Criar tarefa
                      </button>
                    </form>
                  </div>
                </div>
              )}

              {/* HISTORY TAB */}
              {detailTab === "hist" && (
                <div className="space-y-3">
                  {history.length > 0 ? (
                    history.map((h, i) => (
                      <div key={i} className="flex items-center gap-3 text-sm">
                        <div className="w-2 h-2 rounded-full bg-teal-400 flex-shrink-0" />
                        <div>
                          <span className="font-semibold">{h.from_status ?? "início"}</span>
                          <span className="text-slate-400 mx-1">&rarr;</span>
                          <span className="font-semibold">{h.to_status}</span>
                          {h.reason && <span className="text-slate-500 ml-2">| {h.reason}</span>}
                          {h.created_at && <span className="text-slate-400 ml-2 text-xs">{h.created_at.slice(0, 19)}</span>}
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-slate-400">Sem histórico.</p>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Deal selector when no detail shown */}
          {!selectedDealId && dealsList.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <p className="text-sm text-slate-500 mb-2">Selecionar deal para ver detalhes</p>
              <select
                onChange={(e) => setSelectedDealId(e.target.value || null)}
                className="border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-teal-500 w-full max-w-md"
              >
                <option value="">Escolher deal...</option>
                {dealsList.map((d) => (
                  <option key={d.id} value={d.id}>
                    {(d as any).strategy_icon ?? ""} {d.title} ({(d as any).status_label ?? d.status})
                  </option>
                ))}
              </select>
            </div>
          )}
        </>
      )}

      {/* ===== CREATE DEAL TAB ===== */}
      {activeTab === "create" && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 max-w-2xl">
          <h2 className="text-lg font-semibold mb-4">Criar novo deal</h2>

          {createMsg && (
            <div className={`mb-4 px-3 py-2 rounded-lg text-sm ${createMsg.includes("Erro") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
              {createMsg}
            </div>
          )}

          <form onSubmit={handleCreateDeal} className="space-y-4">
            {/* Property */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Propriedade</label>
              <select name="property_id" required className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-teal-500">
                <option value="">Selecionar...</option>
                {properties.map((p) => (
                  <option key={p.id} value={p.id}>{p.label}</option>
                ))}
              </select>
              {properties.length === 0 && (
                <p className="text-xs text-amber-600 mt-1">Sem propriedades. Crie uma primeiro no M1.</p>
              )}
            </div>

            {/* Strategy */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Estratégia</label>
              <select name="strategy" required className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-teal-500">
                {strategies.map((s) => (
                  <option key={s.key} value={s.key}>
                    {s.icon ?? ""} {s.label} {s.description ? `— ${s.description}` : ""}
                  </option>
                ))}
              </select>
            </div>

            {/* Title */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Título do deal</label>
              <input name="title" type="text" required placeholder="Ex: T2 Sacavém — Fix and Flip" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
            </div>

            {/* Numbers */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Preço compra (EUR)</label>
                <input name="purchase_price" type="number" step="any" placeholder="295000" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Preço venda alvo (EUR)</label>
                <input name="target_sale_price" type="number" step="any" placeholder="500000" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Renda mensal (EUR)</label>
                <input name="monthly_rent" type="number" step="any" placeholder="0" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Orçamento obra (EUR)</label>
                <input name="renovation_budget" type="number" step="any" placeholder="98400" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
              </div>
            </div>

            <button
              type="submit"
              disabled={createLoading}
              className="px-6 py-2.5 bg-teal-700 text-white rounded-lg text-sm font-medium hover:bg-teal-800 disabled:opacity-50 transition-colors"
            >
              {createLoading ? "A criar..." : "Criar deal"}
            </button>
          </form>
        </div>
      )}

      {/* ===== MEDIATION TAB ===== */}
      {activeTab === "mediation" && (
        <div className="space-y-6">
          {/* Mediation stats */}
          {medStats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard label="Angariações ativas" value={String(medStats.active_mediations ?? 0)} />
              <StatCard label="Valor em carteira" value={formatEUR(medStats.total_portfolio_value)} />
              <StatCard label="Comissão potencial" value={formatEUR(medStats.potential_commission)} />
              <StatCard label="Taxa conversão" value={medStats.conversion_rate_pct != null ? `${medStats.conversion_rate_pct}%` : "N/D"} />
            </div>
          )}

          {/* Mediation kanban */}
          {medKanban && medKanban.columns && Object.keys(medKanban.columns).length > 0 ? (
            <div>
              <h3 className="text-sm font-semibold text-slate-700 mb-3">Pipeline de mediação venda</h3>
              <div className="flex gap-4 overflow-x-auto pb-4">
                {Object.entries(medKanban.columns).map(([state, deals]) => {
                  const cfg = (medKanban.status_config ?? {})[state] ?? { label: state, color: "#94A3B8", icon: "" };
                  return (
                    <div key={state} className="min-w-[260px] bg-slate-50 rounded-xl p-3 flex-shrink-0">
                      <div
                        className="text-center py-2 px-3 rounded-lg mb-3"
                        style={{
                          backgroundColor: `${cfg.color}15`,
                          borderBottom: `3px solid ${cfg.color}`,
                        }}
                      >
                        <p className="text-sm font-bold text-slate-700">{cfg.icon} {cfg.label}</p>
                        <p className="text-xs text-slate-500">{(deals as Deal[]).length} deal(s)</p>
                      </div>
                      <div className="space-y-2">
                        {(deals as Deal[]).map((deal) => {
                          const days = (deal as any).days_in_status ?? 0;
                          const borderColor = days > 14 ? "#DC2626" : days > 7 ? "#D97706" : "#E2E8F0";
                          const price = deal.target_sale_price ?? deal.purchase_price;
                          return (
                            <div
                              key={deal.id}
                              className="bg-white rounded-lg p-3 border shadow-sm"
                              style={{ borderColor, borderLeftWidth: 4, borderLeftColor: cfg.color }}
                            >
                              <p className="text-sm font-semibold text-slate-900">
                                {(deal as any).strategy_icon ?? ""} {deal.title}
                              </p>
                              <p className="text-xs text-slate-500 mt-1">{formatEUR(price)}</p>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-400">Sem deals de mediação. Crie um na tab &quot;Criar Deal&quot;.</p>
          )}

          {/* Commission calculator */}
          <CommissionCalculator />
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <p className="text-xs text-slate-500 uppercase tracking-wider">{label}</p>
      <p className="text-xl font-bold text-slate-900 mt-1">{value}</p>
    </div>
  );
}

function CommissionCalculator() {
  const [price, setPrice] = useState(295000);
  const [pct, setPct] = useState(5);
  const [shared, setShared] = useState(false);
  const [sharePct, setSharePct] = useState(50);

  const gross = price * pct / 100;
  const vat = gross * 0.23;
  const total = gross + vat;
  const myPart = shared ? total * sharePct / 100 : total;

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6">
      <h3 className="text-sm font-semibold text-slate-700 mb-4">Calculadora de Comissão</h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">Preço de venda (EUR)</label>
          <input
            type="number"
            value={price}
            onChange={(e) => setPrice(Number(e.target.value))}
            className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">Comissão %</label>
          <input
            type="number"
            step="0.5"
            value={pct}
            onChange={(e) => setPct(Number(e.target.value))}
            className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500"
          />
        </div>
        <div className="flex items-end pb-2">
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={shared}
              onChange={(e) => setShared(e.target.checked)}
              className="rounded border-slate-300 text-teal-600 focus:ring-teal-500"
            />
            Partilha com mediador
          </label>
        </div>
        {shared && (
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">A minha parte %</label>
            <input
              type="number"
              value={sharePct}
              onChange={(e) => setSharePct(Number(e.target.value))}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500"
            />
          </div>
        )}
      </div>
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-slate-50 rounded-lg p-3">
          <p className="text-xs text-slate-500">Comissão bruta</p>
          <p className="text-lg font-bold text-slate-900">{formatEUR(gross)}</p>
        </div>
        <div className="bg-slate-50 rounded-lg p-3">
          <p className="text-xs text-slate-500">Com IVA (23%)</p>
          <p className="text-lg font-bold text-slate-900">{formatEUR(total)}</p>
        </div>
        <div className="bg-slate-50 rounded-lg p-3">
          <p className="text-xs text-slate-500">{shared ? "A minha parte" : "Total"}</p>
          <p className="text-lg font-bold text-teal-700">{formatEUR(myPart)}</p>
        </div>
      </div>
    </div>
  );
}
