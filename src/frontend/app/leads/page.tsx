"use client";

import { useState, useEffect, useCallback } from "react";
import { fetcher } from "@/lib/api";
import { formatEUR, cn, GRADE_COLORS } from "@/lib/utils";
import { supabaseGet } from "@/lib/supabase-direct";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://imoia.onrender.com";

interface Lead {
  id: string;
  name: string;
  email?: string;
  phone?: string;
  source?: string;
  stage?: string;
  score?: number;
  grade?: string;
  budget_min?: number;
  budget_max?: number;
  preferred_typology?: string;
  preferred_locations?: string[];
  timeline?: string;
  financing?: string;
  notes?: string;
  created_at?: string;
}

interface LeadStats {
  total_leads?: number;
  leads_this_month?: number;
  avg_score?: number;
  conversion_rate?: number;
}

interface PipelineStage {
  stage: string;
  count: number;
}

interface SourceBreakdown {
  source: string;
  count: number;
}

interface Interaction {
  type?: string;
  content?: string;
  subject?: string;
  created_at?: string;
}

const STAGE_LABELS: Record<string, string> = {
  new: "Novo",
  contacted: "Contactado",
  qualified: "Qualificado",
  visit: "Visita",
  visiting: "Visita",
  proposal: "Proposta",
  negotiation: "Negociação",
  closed_won: "Ganho",
  won: "Ganho",
  closed_lost: "Perdido",
  lost: "Perdido",
};

const STAGE_COLORS: Record<string, string> = {
  new: "#94A3B8",
  contacted: "#2563EB",
  qualified: "#7C3AED",
  visit: "#D97706",
  visiting: "#D97706",
  proposal: "#0F766E",
  negotiation: "#14B8A6",
  closed_won: "#16A34A",
  won: "#16A34A",
  closed_lost: "#DC2626",
  lost: "#DC2626",
};

const ALL_STAGES = ["new", "contacted", "qualified", "visit", "visiting", "proposal", "negotiation", "won", "lost"];
const SOURCES = ["habta.eu", "whatsapp", "idealista", "referral", "instagram", "direct"];
const TYPOLOGIES = ["", "T0", "T1", "T2", "T3", "T4", "T5+"];
const TIMELINES = ["", "imediato", "1-3 meses", "3-6 meses", "6+ meses"];
const FINANCING_OPTS = ["unknown", "cash", "pre_approved", "needs_approval"];

const INTERACTION_ICONS: Record<string, string> = {
  whatsapp_sent: "WA-out",
  whatsapp_received: "WA-in",
  email_sent: "Email",
  call: "Tel",
  visit: "Visita",
  proposal_sent: "Proposta",
  note: "Nota",
  stage_change: "Stage",
  auto_nurture: "Auto",
  listing_view: "View",
};

export default function LeadsPage() {
  const [stats, setStats] = useState<LeadStats | null>(null);
  const [pipeline, setPipeline] = useState<PipelineStage[]>([]);
  const [sourceBreakdown, setSourceBreakdown] = useState<SourceBreakdown[]>([]);
  const [gradesSummary, setGradesSummary] = useState<Record<string, number>>({});
  const [leads, setLeads] = useState<Lead[]>([]);
  const [totalLeads, setTotalLeads] = useState(0);
  const [loading, setLoading] = useState(true);
  const [expandedLead, setExpandedLead] = useState<string | null>(null);
  const [leadTimelines, setLeadTimelines] = useState<Record<string, Interaction[]>>({});

  // Filters
  const [fStage, setFStage] = useState("Todos");
  const [fGrade, setFGrade] = useState("Todos");
  const [fSource, setFSource] = useState("");
  const [fSearch, setFSearch] = useState("");

  // Create form
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newPhone, setNewPhone] = useState("");
  const [newSource, setNewSource] = useState("habta.eu");
  const [newBudgetMin, setNewBudgetMin] = useState(0);
  const [newBudgetMax, setNewBudgetMax] = useState(0);
  const [newTypology, setNewTypology] = useState("");
  const [newTimeline, setNewTimeline] = useState("");
  const [newFinancing, setNewFinancing] = useState("unknown");
  const [newNotes, setNewNotes] = useState("");

  /* ------------------------------------------------------------------ */
  /*  PRIMARY: Load leads from Supabase, with FastAPI fallback           */
  /* ------------------------------------------------------------------ */

  const loadOverview = useCallback(async () => {
    // PRIMARY: Read leads from Supabase to compute stats locally
    const supaLeads = await supabaseGet<Lead>("leads", "select=*&order=created_at.desc");

    if (supaLeads.length > 0) {
      // Compute stats from Supabase data
      const now = new Date();
      const monthStart = new Date(now.getFullYear(), now.getMonth(), 1).toISOString();
      const thisMonthLeads = supaLeads.filter((l) => (l.created_at ?? "") >= monthStart);
      const scores = supaLeads.filter((l) => l.score != null).map((l) => l.score!);
      const avgScore = scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;
      const wonLeads = supaLeads.filter((l) => l.stage === "won" || l.stage === "closed_won");
      const convRate = supaLeads.length > 0 ? (wonLeads.length / supaLeads.length) * 100 : 0;

      setStats({
        total_leads: supaLeads.length,
        leads_this_month: thisMonthLeads.length,
        avg_score: avgScore,
        conversion_rate: convRate,
      });

      // Pipeline stages
      const stageCounts: Record<string, number> = {};
      for (const lead of supaLeads) {
        const stage = lead.stage ?? "new";
        stageCounts[stage] = (stageCounts[stage] ?? 0) + 1;
      }
      setPipeline(Object.entries(stageCounts).map(([stage, count]) => ({ stage, count })));

      // Source breakdown
      const sourceCounts: Record<string, number> = {};
      for (const lead of supaLeads) {
        const source = lead.source ?? "unknown";
        sourceCounts[source] = (sourceCounts[source] ?? 0) + 1;
      }
      setSourceBreakdown(Object.entries(sourceCounts).map(([source, count]) => ({ source, count })));

      // Grade summary
      const grades: Record<string, number> = {};
      for (const lead of supaLeads) {
        const grade = lead.grade ?? "D";
        grades[grade] = (grades[grade] ?? 0) + 1;
      }
      setGradesSummary(grades);
    } else {
      // FALLBACK: FastAPI for overview data
      const [s, p, sb, gr] = await Promise.all([
        fetcher("/api/v1/leads/stats"),
        fetcher("/api/v1/leads/pipeline-summary"),
        fetcher("/api/v1/leads/source-breakdown"),
        fetcher("/api/v1/leads/grades-summary"),
      ]);
      setStats(s);
      setPipeline(p ?? []);
      setSourceBreakdown(sb ?? []);
      setGradesSummary(gr ?? {});
    }
  }, []);

  const loadLeads = useCallback(async () => {
    // PRIMARY: Read leads from Supabase with filters
    let query = "select=*&order=created_at.desc&limit=50";

    if (fStage !== "Todos") {
      const key = Object.entries(STAGE_LABELS).find(([, v]) => v === fStage)?.[0];
      if (key) query += `&stage=eq.${key}`;
    }
    if (fGrade !== "Todos") query += `&grade=eq.${fGrade}`;
    if (fSource) query += `&source=eq.${fSource}`;
    if (fSearch) query += `&name=ilike.*${fSearch}*`;

    const supaLeads = await supabaseGet<Lead>("leads", query);

    if (supaLeads.length > 0 || !fSearch) {
      // Use Supabase data (may be empty if no matches)
      setLeads(supaLeads);
      setTotalLeads(supaLeads.length);
    } else {
      // FALLBACK: FastAPI for filtered leads (supports full-text search)
      const params = new URLSearchParams({ limit: "50" });
      if (fStage !== "Todos") {
        const key = Object.entries(STAGE_LABELS).find(([, v]) => v === fStage)?.[0];
        if (key) params.set("stage", key);
      }
      if (fGrade !== "Todos") params.set("grade", fGrade);
      if (fSource) params.set("source", fSource);
      if (fSearch) params.set("search", fSearch);

      const data = await fetcher(`/api/v1/leads/?${params.toString()}`);
      setLeads(data?.items ?? []);
      setTotalLeads(data?.total ?? 0);
    }
  }, [fStage, fGrade, fSource, fSearch]);

  useEffect(() => {
    setLoading(true);
    Promise.all([loadOverview(), loadLeads()]).then(() => setLoading(false));
  }, [loadOverview, loadLeads]);

  // Write operations: always via FastAPI (needs business logic)
  async function createLead() {
    if (!newName) return;
    const body: Record<string, any> = { name: newName, source: newSource };
    if (newEmail) body.email = newEmail;
    if (newPhone) body.phone = newPhone;
    if (newBudgetMin > 0) body.budget_min = newBudgetMin;
    if (newBudgetMax > 0) body.budget_max = newBudgetMax;
    if (newTypology) body.preferred_typology = newTypology;
    if (newTimeline) body.timeline = newTimeline;
    if (newFinancing !== "unknown") body.financing = newFinancing;
    if (newNotes) body.notes = newNotes;

    const res = await fetch(`${API_BASE}/api/v1/leads/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (res.ok) {
      setShowCreate(false);
      setNewName(""); setNewEmail(""); setNewPhone("");
      setNewBudgetMin(0); setNewBudgetMax(0);
      setNewTypology(""); setNewTimeline(""); setNewFinancing("unknown"); setNewNotes("");
      loadOverview();
      loadLeads();
    }
  }

  async function changeStage(leadId: string, stage: string) {
    await fetch(`${API_BASE}/api/v1/leads/${leadId}/stage`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stage }),
    });
    loadLeads();
    loadOverview();
  }

  async function recalculateScore(leadId: string) {
    await fetch(`${API_BASE}/api/v1/leads/${leadId}/recalculate-score`, { method: "POST" });
    loadLeads();
  }

  async function loadTimeline(leadId: string) {
    const data = await fetcher(`/api/v1/leads/${leadId}/timeline`);
    setLeadTimelines((prev) => ({ ...prev, [leadId]: data ?? [] }));
  }

  async function syncHabta() {
    await fetch(`${API_BASE}/api/v1/leads/sync-habta`, { method: "POST" });
    loadOverview();
    loadLeads();
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-slate-900">M8 — CRM de Leads</h1>
        <div className="text-center py-16 text-slate-400">A carregar...</div>
      </div>
    );
  }

  const uniqueStageLabels = [...new Set(Object.values(STAGE_LABELS))];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">M8 — CRM de Leads</h1>
        <p className="text-sm text-slate-500 mt-1">Gestão do pipeline de compradores e inquilinos</p>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: "Total Leads", value: stats.total_leads ?? 0 },
            { label: "Este Mês", value: stats.leads_this_month ?? 0 },
            { label: "Score Médio", value: (stats.avg_score ?? 0).toFixed(0) },
            { label: "Taxa Conversão", value: `${(stats.conversion_rate ?? 0).toFixed(0)}%` },
          ].map((s) => (
            <div key={s.label} className="bg-white rounded-xl border border-slate-200 p-4">
              <p className="text-xs text-slate-500">{s.label}</p>
              <p className="text-xl font-bold text-slate-900 mt-1">{s.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Pipeline Kanban */}
      {pipeline.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-slate-700 mb-3">Pipeline</h2>
          <div className="flex gap-2 overflow-x-auto pb-2">
            {pipeline.map((stageData) => {
              const label = STAGE_LABELS[stageData.stage] ?? stageData.stage;
              const color = STAGE_COLORS[stageData.stage] ?? "#94A3B8";
              return (
                <div
                  key={stageData.stage}
                  className="min-w-[100px] flex-1 rounded-lg p-3 text-center border-2"
                  style={{ backgroundColor: `${color}10`, borderColor: color }}
                >
                  <p className="text-[10px] font-semibold uppercase tracking-wide" style={{ color }}>{label}</p>
                  <p className="text-2xl font-bold mt-1" style={{ color }}>{stageData.count}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Charts row: Source breakdown + Grade distribution */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Source breakdown */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Leads por Source</h3>
          {sourceBreakdown.length > 0 && sourceBreakdown.some((b) => b.count > 0) ? (
            <div className="space-y-2">
              {sourceBreakdown
                .filter((b) => b.count > 0)
                .sort((a, b) => b.count - a.count)
                .map((b) => {
                  const maxCount = Math.max(...sourceBreakdown.map((s) => s.count), 1);
                  const pct = (b.count / maxCount) * 100;
                  return (
                    <div key={b.source}>
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-slate-600">{b.source}</span>
                        <span className="font-medium text-slate-900">{b.count}</span>
                      </div>
                      <div className="w-full bg-slate-100 rounded-full h-2">
                        <div className="bg-teal-600 h-2 rounded-full" style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  );
                })}
            </div>
          ) : (
            <p className="text-sm text-slate-400">Sem dados de source</p>
          )}
        </div>

        {/* Grade distribution */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Distribuição por Grade</h3>
          {Object.keys(gradesSummary).length > 0 && Object.values(gradesSummary).some((v) => v > 0) ? (
            <div className="flex items-end gap-3 h-40">
              {Object.entries(gradesSummary).map(([grade, count]) => {
                const maxVal = Math.max(...Object.values(gradesSummary), 1);
                const heightPct = (count / maxVal) * 100;
                const color = GRADE_COLORS[grade] ?? "#94A3B8";
                return (
                  <div key={grade} className="flex-1 flex flex-col items-center justify-end h-full">
                    <span className="text-xs font-medium text-slate-700 mb-1">{count}</span>
                    <div
                      className="w-full rounded-t-md min-h-[4px]"
                      style={{ backgroundColor: color, height: `${heightPct}%` }}
                    />
                    <span className="text-xs font-bold mt-1" style={{ color }}>{grade}</span>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-sm text-slate-400">Sem dados de grades</p>
          )}
        </div>
      </div>

      {/* Create Lead / Sync */}
      <div className="flex gap-3 items-center">
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-4 py-2 bg-teal-700 text-white text-sm font-medium rounded-lg hover:bg-teal-800"
        >
          Criar Novo Lead
        </button>
        <button
          onClick={syncHabta}
          className="px-4 py-2 text-sm font-medium text-teal-700 border border-teal-700 rounded-lg hover:bg-teal-50"
        >
          Sincronizar habta.eu
        </button>
        <span className="text-xs text-slate-400">Importa/actualiza leads da tabela contacts do habta.eu</span>
      </div>

      {showCreate && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
          <h3 className="text-sm font-semibold text-slate-700">Criar Novo Lead</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Nome *</label>
              <input type="text" value={newName} onChange={(e) => setNewName(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Budget Min (EUR)</label>
              <input type="number" value={newBudgetMin} onChange={(e) => setNewBudgetMin(Number(e.target.value))}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Email</label>
              <input type="email" value={newEmail} onChange={(e) => setNewEmail(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Budget Max (EUR)</label>
              <input type="number" value={newBudgetMax} onChange={(e) => setNewBudgetMax(Number(e.target.value))}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Phone (+351...)</label>
              <input type="text" value={newPhone} onChange={(e) => setNewPhone(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Tipologia</label>
              <select value={newTypology} onChange={(e) => setNewTypology(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500">
                {TYPOLOGIES.map((t) => <option key={t} value={t}>{t || "—"}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Source</label>
              <select value={newSource} onChange={(e) => setNewSource(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500">
                {SOURCES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Timeline</label>
              <select value={newTimeline} onChange={(e) => setNewTimeline(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500">
                {TIMELINES.map((t) => <option key={t} value={t}>{t || "—"}</option>)}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Financiamento</label>
              <select value={newFinancing} onChange={(e) => setNewFinancing(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500">
                {FINANCING_OPTS.map((f) => <option key={f} value={f}>{f}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Notas</label>
              <textarea value={newNotes} onChange={(e) => setNewNotes(e.target.value)} rows={2}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" />
            </div>
          </div>
          <div className="flex gap-3">
            <button onClick={createLead} className="px-4 py-2 bg-teal-700 text-white text-sm font-medium rounded-lg hover:bg-teal-800">
              Criar Lead
            </button>
            <button onClick={() => setShowCreate(false)} className="px-4 py-2 text-sm text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50">
              Cancelar
            </button>
          </div>
        </div>
      )}

      {/* Filters */}
      <div>
        <h2 className="text-sm font-semibold text-slate-700 mb-3">Leads</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <select value={fStage} onChange={(e) => setFStage(e.target.value)}
            className="px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500">
            <option value="Todos">Todos os stages</option>
            {uniqueStageLabels.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
          <select value={fGrade} onChange={(e) => setFGrade(e.target.value)}
            className="px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500">
            <option value="Todos">Todos os grades</option>
            {["A", "B", "C", "D", "F"].map((g) => <option key={g} value={g}>{g}</option>)}
          </select>
          <input type="text" placeholder="Filtrar source..." value={fSource} onChange={(e) => setFSource(e.target.value)}
            className="px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" />
          <input type="text" placeholder="Pesquisar..." value={fSearch} onChange={(e) => setFSearch(e.target.value)}
            className="px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" />
        </div>
        <p className="text-xs text-slate-400 mb-3">{totalLeads} leads encontrados</p>
      </div>

      {/* Leads list */}
      {leads.length === 0 ? (
        <div className="text-center py-12 text-slate-400">
          <p>Nenhum lead encontrado.</p>
          <p className="text-sm mt-1">Crie um acima ou sincronize com habta.eu.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {leads.map((lead) => {
            const gradeColor = GRADE_COLORS[lead.grade ?? "D"] ?? GRADE_COLORS.D;
            const stageLabel = STAGE_LABELS[lead.stage ?? ""] ?? lead.stage ?? "";
            const stageColor = STAGE_COLORS[lead.stage ?? ""] ?? "#94A3B8";
            const isExpanded = expandedLead === lead.id;

            let budget = "";
            if (lead.budget_min || lead.budget_max) {
              const bmin = lead.budget_min ? `${(lead.budget_min / 1000).toFixed(0)}k` : "?";
              const bmax = lead.budget_max ? `${(lead.budget_max / 1000).toFixed(0)}k` : "?";
              budget = `${bmin}-${bmax} EUR`;
            }

            return (
              <div
                key={lead.id}
                className="bg-white rounded-xl border border-slate-200 overflow-hidden"
                style={{ borderLeftWidth: 4, borderLeftColor: gradeColor }}
              >
                <button
                  onClick={() => {
                    setExpandedLead(isExpanded ? null : lead.id);
                    if (!isExpanded && !leadTimelines[lead.id]) loadTimeline(lead.id);
                  }}
                  className="w-full px-5 py-4 flex items-center justify-between hover:bg-slate-50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-semibold text-slate-900">{lead.name}</span>
                    <span
                      className="text-[10px] font-bold px-2 py-0.5 rounded"
                      style={{ backgroundColor: `${gradeColor}15`, color: gradeColor }}
                    >
                      {lead.grade ?? "D"} {lead.score != null && `(${lead.score})`}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span
                      className="text-xs font-medium px-2 py-0.5 rounded"
                      style={{ backgroundColor: `${stageColor}15`, color: stageColor }}
                    >
                      {stageLabel}
                    </span>
                    <span className="text-xs text-slate-500">{lead.source ?? "—"}</span>
                    {lead.preferred_typology && (
                      <span className="text-xs bg-slate-100 px-2 py-0.5 rounded text-slate-500">{lead.preferred_typology}</span>
                    )}
                    {budget && <span className="text-xs text-slate-500">{budget}</span>}
                    <svg
                      className={cn("w-4 h-4 text-slate-400 transition-transform", isExpanded && "rotate-180")}
                      fill="none" viewBox="0 0 24 24" stroke="currentColor"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                </button>

                {isExpanded && (
                  <div className="px-5 pb-5 border-t border-slate-100 pt-4">
                    <div className="grid grid-cols-3 gap-4">
                      {/* Contact info */}
                      <div className="space-y-2 text-sm">
                        <p className="text-slate-500">Email: <span className="text-slate-900">{lead.email || "—"}</span></p>
                        <p className="text-slate-500">Phone: <span className="text-slate-900">{lead.phone || "—"}</span></p>
                        <p className="text-slate-500">Tipologia: <span className="text-slate-900">{lead.preferred_typology || "—"}</span></p>
                        {lead.preferred_locations && lead.preferred_locations.length > 0 && (
                          <p className="text-slate-500">Localizações: <span className="text-slate-900">{lead.preferred_locations.join(", ")}</span></p>
                        )}
                        {lead.notes && (
                          <p className="text-slate-500">Notas: <span className="text-slate-900">{lead.notes.slice(0, 200)}</span></p>
                        )}
                      </div>

                      {/* Grade badge */}
                      <div className="flex justify-center">
                        <div
                          className="w-24 h-24 rounded-xl flex flex-col items-center justify-center border-2"
                          style={{ backgroundColor: `${gradeColor}10`, borderColor: gradeColor }}
                        >
                          <span className="text-3xl font-bold" style={{ color: gradeColor }}>{lead.grade ?? "D"}</span>
                          <span className="text-sm" style={{ color: gradeColor }}>{lead.score ?? 0} pts</span>
                        </div>
                      </div>

                      {/* Stage change + actions */}
                      <div className="space-y-3">
                        <div>
                          <label className="block text-xs text-slate-500 mb-1">Mudar Stage</label>
                          <select
                            defaultValue={lead.stage}
                            onChange={(e) => changeStage(lead.id, e.target.value)}
                            className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                          >
                            {ALL_STAGES.map((s) => (
                              <option key={s} value={s}>{STAGE_LABELS[s] ?? s}</option>
                            ))}
                          </select>
                        </div>
                        <button
                          onClick={() => recalculateScore(lead.id)}
                          className="w-full px-3 py-2 text-xs font-medium text-teal-700 border border-teal-700 rounded-lg hover:bg-teal-50"
                        >
                          Recalcular Score
                        </button>
                      </div>
                    </div>

                    {/* Timeline */}
                    <div className="mt-4 pt-4 border-t border-slate-100">
                      <h4 className="text-sm font-semibold text-slate-700 mb-2">Timeline</h4>
                      {leadTimelines[lead.id]?.length ? (
                        <div className="space-y-2 max-h-48 overflow-y-auto">
                          {leadTimelines[lead.id].slice(0, 10).map((inter, idx) => {
                            const ts = (inter.created_at ?? "").slice(0, 16);
                            const content = inter.content || inter.subject || "";
                            const truncated = content.length > 100 ? content.slice(0, 100) + "..." : content;
                            const iconLabel = INTERACTION_ICONS[inter.type ?? ""] ?? "---";
                            return (
                              <div key={idx} className="flex items-start gap-2 text-xs">
                                <span className="bg-slate-100 px-1.5 py-0.5 rounded text-slate-500 font-mono whitespace-nowrap">{iconLabel}</span>
                                <span className="text-slate-400 whitespace-nowrap">{ts}</span>
                                <span className="font-medium text-slate-600">{inter.type}</span>
                                {truncated && <span className="text-slate-500">— {truncated}</span>}
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <p className="text-xs text-slate-400">Sem interacções</p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
