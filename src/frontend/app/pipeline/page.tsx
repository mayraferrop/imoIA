"use client";

import { useState, useEffect, useCallback } from "react";
import { formatEUR, GRADE_COLORS } from "@/lib/utils";
import { supabaseGet } from "@/lib/supabase";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
type DetailTab = "resumo" | "propostas" | "tasks" | "hist";

/* ------------------------------------------------------------------ */
/*  Status config for kanban columns (used when reading from Supabase) */
/* ------------------------------------------------------------------ */
const DEFAULT_STATUS_CONFIG: Record<string, { label: string; color: string; icon: string }> = {
  triagem: { label: "Triagem", color: "#94A3B8", icon: "" },
  analise: { label: "Analise", color: "#2563EB", icon: "" },
  proposta: { label: "Proposta", color: "#7C3AED", icon: "" },
  negociacao: { label: "Negociacao", color: "#D97706", icon: "" },
  cpcv: { label: "CPCV", color: "#14B8A6", icon: "" },
  escritura: { label: "Escritura", color: "#0F766E", icon: "" },
  obra: { label: "Obra", color: "#F59E0B", icon: "" },
  venda: { label: "Venda", color: "#16A34A", icon: "" },
  concluido: { label: "Concluido", color: "#16A34A", icon: "" },
  descartado: { label: "Descartado", color: "#DC2626", icon: "" },
  em_pausa: { label: "Em Pausa", color: "#94A3B8", icon: "" },
  angariacao: { label: "Angariacao", color: "#2563EB", icon: "" },
  preparacao: { label: "Preparacao", color: "#7C3AED", icon: "" },
  marketing: { label: "Marketing", color: "#D97706", icon: "" },
  visitas: { label: "Visitas", color: "#14B8A6", icon: "" },
  fecho: { label: "Fecho", color: "#0F766E", icon: "" },
};

export default function PipelinePage() {
  const [activeTab, setActiveTab] = useState<PipelineTab>("kanban");
  const [kanban, setKanban] = useState<KanbanData | null>(null);
  const [stats, setStats] = useState<DealStats | null>(null);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [strategyFilter, setStrategyFilter] = useState("");

  // Deal detail
  const [dealsList, setDealsList] = useState<Deal[]>([]);
  const [selectedDealId, setSelectedDealId] = useState<string | null>(null);
  const [selectedDeal, setSelectedDeal] = useState<Deal | null>(null);
  const [detailTab, setDetailTab] = useState<DetailTab>("resumo");
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [nextActions, setNextActions] = useState<NextAction[]>([]);

  // Create deal
  const [createMsg, setCreateMsg] = useState("");
  const [createLoading, setCreateLoading] = useState(false);
  const [properties, setProperties] = useState<{ id: string; label: string }[]>([]);

  // Advance
  const [advanceLoading, setAdvanceLoading] = useState(false);
  const [advanceMsg, setAdvanceMsg] = useState("");
  const [pendingAction, setPendingAction] = useState<{ status: string; label: string } | null>(null);
  const [advanceReason, setAdvanceReason] = useState("");

  // Proposal creation
  const [proposalMsg, setProposalMsg] = useState("");

  // Mediation
  const [medKanban, setMedKanban] = useState<KanbanData | null>(null);
  const [medStats, setMedStats] = useState<Record<string, any> | null>(null);

  /* ------------------------------------------------------------------ */
  /*  PRIMARY: Load deals from Supabase, group into kanban columns       */
  /* ------------------------------------------------------------------ */
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      // PRIMARY: Supabase direct query for deals (instant, no cold start)
      const query = strategyFilter
        ? `select=*,properties(*)&order=created_at.desc&investment_strategy=eq.${strategyFilter}`
        : "select=*,properties(*)&order=created_at.desc";
      const supaDeals = await supabaseGet<Deal>("deals", query);

      if (supaDeals.length > 0) {
        // Group deals by current_state for kanban columns
        const columns: Record<string, Deal[]> = {};
        for (const deal of supaDeals) {
          const state = deal.current_state ?? deal.status ?? "triagem";
          if (!columns[state]) columns[state] = [];
          // Map properties relation to property for compatibility
          if (deal.properties && !deal.property) {
            (deal as any).property = deal.properties;
          }
          columns[state].push(deal);
        }

        // Build status config from DEFAULT_STATUS_CONFIG
        const statusConfig: Record<string, { label: string; color: string; icon: string }> = {};
        for (const state of Object.keys(columns)) {
          statusConfig[state] = DEFAULT_STATUS_CONFIG[state] ?? { label: state, color: "#94A3B8", icon: "" };
        }

        setKanban({ columns, total_deals: supaDeals.length, status_config: statusConfig });
        setDealsList(supaDeals);

        // Calculate basic stats from Supabase data
        const active = supaDeals.filter((d) => !["concluido", "descartado"].includes(d.current_state ?? d.status ?? ""));
        const completed = supaDeals.filter((d) => (d.current_state ?? d.status) === "concluido");
        const discarded = supaDeals.filter((d) => (d.current_state ?? d.status) === "descartado");
        const totalInvested = supaDeals.reduce((sum, d) => sum + (d.purchase_price ?? 0), 0);
        const totalRent = supaDeals.reduce((sum, d) => sum + (d.monthly_rent ?? 0), 0);
        setStats({
          active_deals: active.length,
          completed_deals: completed.length,
          discarded_deals: discarded.length,
          total_invested: totalInvested,
          total_monthly_rent: totalRent,
        });
      } else {
        // FALLBACK: FastAPI (handles cold start gracefully)
        const params = strategyFilter ? `?strategy=${strategyFilter}` : "";
        const [kanbanRes, statsRes, dealsRes] = await Promise.all([
          fetch(`${API_BASE}/api/v1/deals/kanban${params}`),
          fetch(`${API_BASE}/api/v1/deals/stats`),
          fetch(`${API_BASE}/api/v1/deals/?limit=100`),
        ]);
        if (kanbanRes.ok) setKanban(await kanbanRes.json());
        if (statsRes.ok) setStats(await statsRes.json());
        if (dealsRes.ok) {
          const data = await dealsRes.json();
          setDealsList(data.items ?? []);
        }
      }

      // Always fetch strategies from FastAPI (static config, not in DB)
      try {
        const strategiesRes = await fetch(`${API_BASE}/api/v1/deals/strategies`);
        if (strategiesRes.ok) setStrategies(await strategiesRes.json());
      } catch {
        // strategies not critical
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [strategyFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Fetch properties for create form
  useEffect(() => {
    if (activeTab === "create") {
      // PRIMARY: Supabase for properties list
      supabaseGet("properties", "select=id,municipality,typology,asking_price&order=created_at.desc&limit=100")
        .then((items) => {
          if (items.length > 0) {
            setProperties(
              items.map((p: any) => ({
                id: p.id,
                label: `${p.municipality ?? "?"} — ${p.typology ?? "?"} (${formatEUR(p.asking_price)})`,
              }))
            );
          } else {
            // FALLBACK: FastAPI
            fetch(`${API_BASE}/api/v1/properties/?limit=100`)
              .then((r) => r.ok ? r.json() : null)
              .then((data) => {
                if (data?.items) {
                  setProperties(
                    data.items.map((p: any) => ({
                      id: p.id,
                      label: `${p.municipality ?? "?"} — ${p.typology ?? "?"} (${formatEUR(p.asking_price)})`,
                    }))
                  );
                }
              })
              .catch(() => {});
          }
        });
    }
  }, [activeTab]);

  // Fetch mediation data
  useEffect(() => {
    if (activeTab === "mediation") {
      // PRIMARY: Supabase for mediation deals
      supabaseGet<Deal>("deals", "select=*,properties(*)&investment_strategy=eq.mediacao_venda&order=created_at.desc")
        .then((medDeals) => {
          if (medDeals.length > 0) {
            const columns: Record<string, Deal[]> = {};
            for (const deal of medDeals) {
              const state = deal.current_state ?? deal.status ?? "triagem";
              if (!columns[state]) columns[state] = [];
              columns[state].push(deal);
            }
            const statusConfig: Record<string, { label: string; color: string; icon: string }> = {};
            for (const state of Object.keys(columns)) {
              statusConfig[state] = DEFAULT_STATUS_CONFIG[state] ?? { label: state, color: "#94A3B8", icon: "" };
            }
            setMedKanban({ columns, total_deals: medDeals.length, status_config: statusConfig });
          } else {
            // FALLBACK: FastAPI
            fetch(`${API_BASE}/api/v1/deals/kanban?strategy=mediacao_venda`)
              .then(async (kRes) => { if (kRes.ok) setMedKanban(await kRes.json()); })
              .catch(() => {});
          }
        });

      // Stats always from FastAPI (computed endpoint)
      fetch(`${API_BASE}/api/v1/deals/stats/mediation`)
        .then(async (sRes) => { if (sRes.ok) setMedStats(await sRes.json()); })
        .catch(() => {});
    }
  }, [activeTab]);

  // Fetch deal detail — keep FastAPI for detail, proposals, history, next-actions (business logic)
  useEffect(() => {
    if (!selectedDealId) {
      setSelectedDeal(null);
      return;
    }
    Promise.all([
      fetch(`${API_BASE}/api/v1/deals/${selectedDealId}`),
      fetch(`${API_BASE}/api/v1/deals/${selectedDealId}/proposals`),
      fetch(`${API_BASE}/api/v1/deals/${selectedDealId}/history`),
      fetch(`${API_BASE}/api/v1/deals/${selectedDealId}/next-actions`),
    ]).then(async ([dealRes, propRes, histRes, actRes]) => {
      if (dealRes.ok) setSelectedDeal(await dealRes.json());
      if (propRes.ok) setProposals(await propRes.json());
      else setProposals([]);
      if (histRes.ok) setHistory(await histRes.json());
      else setHistory([]);
      if (actRes.ok) {
        const data = await actRes.json();
        setNextActions(data.next_statuses ?? []);
      } else {
        setNextActions([]);
      }
    }).catch(() => {});
  }, [selectedDealId]);

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
      const res = await fetch(`${API_BASE}/api/v1/deals/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const data = await res.json();
        setCreateMsg(`Deal criado: ${data.title ?? data.id}`);
        (e.target as HTMLFormElement).reset();
        fetchData();
      } else {
        setCreateMsg("Erro ao criar deal.");
      }
    } catch {
      setCreateMsg("Erro de comunicacao.");
    } finally {
      setCreateLoading(false);
    }
  }

  async function handleAdvance(targetStatus: string, reason?: string) {
    if (!selectedDealId) return;
    setAdvanceLoading(true);
    setAdvanceMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/v1/deals/${selectedDealId}/advance`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_status: targetStatus, reason: reason || null }),
      });
      if (res.ok) {
        setAdvanceMsg(`Avancado para ${targetStatus}`);
        setPendingAction(null);
        setAdvanceReason("");
        fetchData();
        // Refresh detail
        setSelectedDealId((prev) => prev); // trigger re-fetch
      } else {
        setAdvanceMsg("Erro ao avancar deal.");
      }
    } catch {
      setAdvanceMsg("Erro de comunicacao.");
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
      const res = await fetch(`${API_BASE}/api/v1/deals/${selectedDealId}/proposals`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        setProposalMsg("Proposta criada!");
        (e.target as HTMLFormElement).reset();
        // Refresh proposals
        const pRes = await fetch(`${API_BASE}/api/v1/deals/${selectedDealId}/proposals`);
        if (pRes.ok) setProposals(await pRes.json());
      } else {
        setProposalMsg("Erro ao criar proposta.");
      }
    } catch {
      setProposalMsg("Erro de comunicacao.");
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
          <StatCard label="Deals activos" value={String(stats.active_deals ?? 0)} />
          <StatCard label="Concluidos" value={String(stats.completed_deals ?? 0)} />
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
          ["mediation", "Mediacao"],
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
              <option value="">Todas as estrategias</option>
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
                              {(deal as any).strategy_icon ?? ""} {deal.title || deal.property?.municipality || (deal.properties as any)?.municipality || "Sem titulo"}
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
                  onClick={() => { setSelectedDealId(null); setSelectedDeal(null); setPendingAction(null); setAdvanceMsg(""); }}
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
                  ["tasks", "Tasks"],
                  ["hist", "Historico"],
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
                      <p><span className="text-slate-500">Estrategia:</span> {(selectedDeal as any).strategy_icon ?? ""} {(selectedDeal as any).strategy_label ?? selectedDeal.strategy}</p>
                      <p><span className="text-slate-500">Estado:</span> {(selectedDeal as any).status_icon ?? ""} {(selectedDeal as any).status_label ?? selectedDeal.status}</p>
                      <p><span className="text-slate-500">Progresso:</span> {((selectedDeal as any).progress_pct ?? 0).toFixed(0)}%</p>
                      {selectedDeal.purchase_price && <p><span className="text-slate-500">Compra:</span> {formatEUR(selectedDeal.purchase_price)}</p>}
                      {selectedDeal.target_sale_price && <p><span className="text-slate-500">Venda alvo:</span> {formatEUR(selectedDeal.target_sale_price)}</p>}
                      {selectedDeal.renovation_budget && <p><span className="text-slate-500">Orcamento obra:</span> {formatEUR(selectedDeal.renovation_budget)}</p>}
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
                    <p className="text-sm font-semibold text-slate-700 mb-3">Proximas accoes</p>

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
                          <p className="text-xs text-slate-400">Sem accoes disponiveis</p>
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
                            <p className="text-xs text-slate-400 mt-1">Condicoes: {p.conditions}</p>
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
                          <label className="block text-xs font-medium text-slate-600 mb-1">Condicoes</label>
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

              {/* TASKS TAB */}
              {detailTab === "tasks" && (
                <div>
                  <p className="text-sm text-slate-400">Tarefas serao carregadas via API /api/v1/deals/tasks/upcoming quando disponivel.</p>
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
                          <span className="font-semibold">{h.from_status ?? "inicio"}</span>
                          <span className="text-slate-400 mx-1">&rarr;</span>
                          <span className="font-semibold">{h.to_status}</span>
                          {h.reason && <span className="text-slate-500 ml-2">| {h.reason}</span>}
                          {h.created_at && <span className="text-slate-400 ml-2 text-xs">{h.created_at.slice(0, 19)}</span>}
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-slate-400">Sem historico.</p>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Deal selector when no detail shown */}
          {!selectedDealId && dealsList.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <p className="text-sm text-slate-500 mb-2">Seleccionar deal para ver detalhes</p>
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
                <option value="">Seleccionar...</option>
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
              <label className="block text-sm font-medium text-slate-700 mb-1">Estrategia</label>
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
              <label className="block text-sm font-medium text-slate-700 mb-1">Titulo do deal</label>
              <input name="title" type="text" required placeholder="Ex: T2 Sacavem — Fix and Flip" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
            </div>

            {/* Numbers */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Preco compra (EUR)</label>
                <input name="purchase_price" type="number" step="any" placeholder="295000" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Preco venda alvo (EUR)</label>
                <input name="target_sale_price" type="number" step="any" placeholder="500000" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Renda mensal (EUR)</label>
                <input name="monthly_rent" type="number" step="any" placeholder="0" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Orcamento obra (EUR)</label>
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
              <StatCard label="Angariacoes activas" value={String(medStats.active_mediations ?? 0)} />
              <StatCard label="Valor em carteira" value={formatEUR(medStats.total_portfolio_value)} />
              <StatCard label="Comissao potencial" value={formatEUR(medStats.potential_commission)} />
              <StatCard label="Taxa conversao" value={medStats.conversion_rate_pct != null ? `${medStats.conversion_rate_pct}%` : "N/D"} />
            </div>
          )}

          {/* Mediation kanban */}
          {medKanban && medKanban.columns && Object.keys(medKanban.columns).length > 0 ? (
            <div>
              <h3 className="text-sm font-semibold text-slate-700 mb-3">Pipeline de mediacao venda</h3>
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
            <p className="text-sm text-slate-400">Sem deals de mediacao. Crie um na tab &quot;Criar Deal&quot;.</p>
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
      <h3 className="text-sm font-semibold text-slate-700 mb-4">Calculadora de Comissao</h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">Preco de venda (EUR)</label>
          <input
            type="number"
            value={price}
            onChange={(e) => setPrice(Number(e.target.value))}
            className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">Comissao %</label>
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
          <p className="text-xs text-slate-500">Comissao bruta</p>
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
