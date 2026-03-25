"use client";

import { useState, useEffect, useCallback } from "react";
import { formatEUR, GRADE_COLORS } from "@/lib/utils";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Property {
  id: string;
  source: string;
  municipality: string;
  district?: string;
  parish?: string;
  address?: string;
  property_type?: string;
  typology?: string;
  area_m2?: number;
  asking_price?: number;
  price_per_m2?: number;
  deal_grade?: string;
  deal_score?: number;
  confidence?: number;
  opportunity_type?: string;
  description?: string;
  url?: string;
  status?: string;
  created_at: string;
}

interface IngestStats {
  groups?: { total: number; active: number };
  messages?: number;
  opportunities?: number;
  grade_distribution?: Record<string, number>;
  top_districts?: { district: string; count: number }[];
}

const OPP_TYPE_LABELS: Record<string, string> = {
  abaixo_mercado: "Abaixo Mercado",
  venda_urgente: "Venda Urgente",
  off_market: "Off-Market",
  reabilitacao: "Reabilitacao",
  leilao: "Leilao",
  predio_inteiro: "Predio Inteiro",
  terreno_viabilidade: "Terreno c/ Viab.",
  yield_alto: "Yield Alto",
  outro: "Outro",
};

export default function PropertiesPage() {
  const [properties, setProperties] = useState<Property[]>([]);
  const [stats, setStats] = useState<IngestStats | null>(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [triggerLoading, setTriggerLoading] = useState(false);
  const [triggerMsg, setTriggerMsg] = useState("");
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createMsg, setCreateMsg] = useState("");

  // Filters
  const [filterMunicipality, setFilterMunicipality] = useState("");
  const [filterType, setFilterType] = useState("");
  const [filterGrade, setFilterGrade] = useState("");
  const [filterMinPrice, setFilterMinPrice] = useState("");
  const [filterMaxPrice, setFilterMaxPrice] = useState("");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [propsRes, statsRes] = await Promise.all([
        fetch(`${API_BASE}/api/v1/properties/?limit=50`),
        fetch(`${API_BASE}/api/v1/ingest/stats`),
      ]);
      if (propsRes.ok) {
        const data = await propsRes.json();
        setProperties(data.items ?? []);
        setTotal(data.total ?? 0);
      }
      if (statsRes.ok) {
        setStats(await statsRes.json());
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Client-side filtering
  const filtered = properties.filter((p) => {
    if (filterMunicipality && !p.municipality?.toLowerCase().includes(filterMunicipality.toLowerCase())) return false;
    if (filterType && p.property_type !== filterType) return false;
    if (filterGrade && p.deal_grade !== filterGrade) return false;
    if (filterMinPrice && (p.asking_price ?? 0) < Number(filterMinPrice)) return false;
    if (filterMaxPrice && (p.asking_price ?? 0) > Number(filterMaxPrice)) return false;
    return true;
  });

  async function handleTriggerPipeline() {
    setTriggerLoading(true);
    setTriggerMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/v1/ingest/trigger`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setTriggerMsg(
          `Pipeline concluido: ${data.messages_fetched ?? 0} mensagens, ${data.opportunities_found ?? 0} oportunidades`
        );
        fetchData();
      } else {
        setTriggerMsg("Erro ao executar pipeline.");
      }
    } catch {
      setTriggerMsg("Erro de comunicacao com a API.");
    } finally {
      setTriggerLoading(false);
    }
  }

  async function handleCreateProperty(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setCreateLoading(true);
    setCreateMsg("");
    const fd = new FormData(e.currentTarget);
    const body: Record<string, any> = {};
    if (fd.get("municipality")) body.municipality = fd.get("municipality");
    if (fd.get("district")) body.district = fd.get("district");
    if (fd.get("parish")) body.parish = fd.get("parish");
    if (fd.get("property_type")) body.property_type = fd.get("property_type");
    if (fd.get("typology")) body.typology = fd.get("typology");
    if (fd.get("asking_price")) body.asking_price = Number(fd.get("asking_price"));
    if (fd.get("gross_area_m2")) body.gross_area_m2 = Number(fd.get("gross_area_m2"));
    if (fd.get("bedrooms")) body.bedrooms = Number(fd.get("bedrooms"));
    if (fd.get("condition")) body.condition = fd.get("condition");
    if (fd.get("notes")) body.notes = fd.get("notes");
    if (fd.get("contact_name")) body.contact_name = fd.get("contact_name");
    if (fd.get("contact_phone")) body.contact_phone = fd.get("contact_phone");

    try {
      const res = await fetch(`${API_BASE}/api/v1/properties/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        setCreateMsg("Propriedade criada com sucesso!");
        setShowCreateForm(false);
        (e.target as HTMLFormElement).reset();
        fetchData();
      } else {
        setCreateMsg("Erro ao criar propriedade.");
      }
    } catch {
      setCreateMsg("Erro de comunicacao.");
    } finally {
      setCreateLoading(false);
    }
  }

  // Stats
  const totalGroups = stats?.groups?.total ?? 0;
  const activeGroups = stats?.groups?.active ?? 0;
  const totalMsgs = stats?.messages ?? 0;
  const totalOpps = stats?.opportunities ?? 0;
  const conversion = totalMsgs > 0 ? ((totalOpps / totalMsgs) * 100).toFixed(1) : "0.0";

  // Grade distribution
  const gradeDistribution = stats?.grade_distribution ?? {};
  const gradeEntries = Object.entries(gradeDistribution);
  const maxGradeCount = Math.max(...gradeEntries.map(([, v]) => v), 1);

  // Unique values for filters
  const municipalities = [...new Set(properties.map((p) => p.municipality).filter(Boolean))].sort();
  const propertyTypes = [...new Set(properties.map((p) => p.property_type).filter(Boolean))].sort();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">M1 — Propriedades</h1>
          <p className="text-sm text-slate-500 mt-1">{total} propriedades no sistema</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => setShowCreateForm(!showCreateForm)}
            className="px-4 py-2.5 bg-white border border-slate-300 text-slate-700 rounded-lg text-sm font-medium hover:bg-slate-50 transition-colors"
          >
            + Nova propriedade
          </button>
          <button
            onClick={handleTriggerPipeline}
            disabled={triggerLoading}
            className="px-4 py-2.5 bg-teal-700 text-white rounded-lg text-sm font-medium hover:bg-teal-800 disabled:opacity-50 transition-colors"
          >
            {triggerLoading ? "A executar..." : "Rodar pipeline"}
          </button>
        </div>
      </div>

      {/* Trigger message */}
      {triggerMsg && (
        <div className={`px-4 py-3 rounded-lg text-sm ${triggerMsg.includes("Erro") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
          {triggerMsg}
        </div>
      )}

      {/* Create message */}
      {createMsg && (
        <div className={`px-4 py-3 rounded-lg text-sm ${createMsg.includes("Erro") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
          {createMsg}
        </div>
      )}

      {/* Stats KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Grupos" value={String(totalGroups)} sub={`${activeGroups} activos`} />
        <StatCard label="Mensagens" value={totalMsgs.toLocaleString("pt-PT")} />
        <StatCard label="Oportunidades" value={String(totalOpps)} />
        <StatCard label="Taxa conversao" value={`${conversion}%`} />
      </div>

      {/* Grade distribution chart */}
      {gradeEntries.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">Distribuicao por Deal Grade</h2>
          <div className="flex items-end gap-3 h-32">
            {gradeEntries.map(([grade, count]) => {
              const color = GRADE_COLORS[grade] ?? GRADE_COLORS.D;
              const heightPct = (count / maxGradeCount) * 100;
              return (
                <div key={grade} className="flex flex-col items-center flex-1">
                  <span className="text-xs font-bold text-slate-600 mb-1">{count}</span>
                  <div
                    className="w-full rounded-t-md transition-all"
                    style={{ backgroundColor: color, height: `${Math.max(heightPct, 4)}%`, minHeight: 4 }}
                  />
                  <span className="text-xs font-bold mt-1" style={{ color }}>
                    {grade}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Create property form */}
      {showCreateForm && (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">Nova propriedade</h2>
          <form onSubmit={handleCreateProperty} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <FormField name="municipality" label="Concelho" placeholder="Lisboa" type="text" />
              <FormField name="district" label="Distrito" placeholder="Lisboa" type="text" />
              <FormField name="parish" label="Freguesia" placeholder="Arroios" type="text" />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Tipo de imovel</label>
                <select
                  name="property_type"
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-500 focus:border-teal-500 outline-none bg-white"
                >
                  <option value="">Seleccionar</option>
                  <option value="apartamento">Apartamento</option>
                  <option value="moradia">Moradia</option>
                  <option value="terreno">Terreno</option>
                  <option value="predio">Predio</option>
                  <option value="armazem">Armazem</option>
                </select>
              </div>
              <FormField name="typology" label="Tipologia" placeholder="T2" type="text" />
              <FormField name="asking_price" label="Preco pedido (EUR)" placeholder="150000" type="number" />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <FormField name="gross_area_m2" label="Area bruta (m2)" placeholder="80" type="number" />
              <FormField name="bedrooms" label="Quartos" placeholder="2" type="number" />
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Estado</label>
                <select
                  name="condition"
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-500 focus:border-teal-500 outline-none bg-white"
                >
                  <option value="">Seleccionar</option>
                  <option value="usado">Usado</option>
                  <option value="renovado">Renovado</option>
                  <option value="novo">Novo</option>
                  <option value="para_renovar">Para renovar</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormField name="contact_name" label="Contacto" placeholder="Nome" type="text" />
              <FormField name="contact_phone" label="Telefone" placeholder="+351..." type="text" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Notas</label>
              <textarea
                name="notes"
                rows={2}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-500 focus:border-teal-500 outline-none"
                placeholder="Notas sobre a propriedade..."
              />
            </div>
            <div className="flex gap-3">
              <button
                type="submit"
                disabled={createLoading}
                className="px-6 py-2.5 bg-teal-700 text-white rounded-lg text-sm font-medium hover:bg-teal-800 disabled:opacity-50 transition-colors"
              >
                {createLoading ? "A criar..." : "Criar propriedade"}
              </button>
              <button
                type="button"
                onClick={() => setShowCreateForm(false)}
                className="px-6 py-2.5 bg-slate-100 text-slate-600 rounded-lg text-sm font-medium hover:bg-slate-200 transition-colors"
              >
                Cancelar
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Concelho</label>
            <select
              value={filterMunicipality}
              onChange={(e) => setFilterMunicipality(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-teal-500"
            >
              <option value="">Todos</option>
              {municipalities.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Tipo</label>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-teal-500"
            >
              <option value="">Todos</option>
              {propertyTypes.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Deal Grade</label>
            <select
              value={filterGrade}
              onChange={(e) => setFilterGrade(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-teal-500"
            >
              <option value="">Todos</option>
              {["A", "B", "C", "D", "F"].map((g) => (
                <option key={g} value={g}>{g}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Preco min</label>
            <input
              type="number"
              value={filterMinPrice}
              onChange={(e) => setFilterMinPrice(e.target.value)}
              placeholder="0"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Preco max</label>
            <input
              type="number"
              value={filterMaxPrice}
              onChange={(e) => setFilterMaxPrice(e.target.value)}
              placeholder="999999"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500"
            />
          </div>
        </div>
      </div>

      {/* Property count */}
      <p className="text-xs text-slate-400">{filtered.length} propriedade(s) encontrada(s)</p>

      {/* Property cards */}
      {loading ? (
        <div className="text-center py-16 text-slate-400">A carregar...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((p) => {
            const gradeColor = GRADE_COLORS[p.deal_grade ?? "D"] ?? GRADE_COLORS.D;
            const oppLabel = OPP_TYPE_LABELS[p.opportunity_type ?? ""] ?? p.opportunity_type;
            return (
              <div
                key={p.id}
                className="bg-white rounded-xl border border-slate-200 overflow-hidden hover:shadow-md transition-shadow"
                style={{ borderLeftWidth: 4, borderLeftColor: gradeColor }}
              >
                <div className="p-5">
                  {/* Header */}
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="font-semibold text-slate-900">{p.municipality}</h3>
                      {p.parish && <p className="text-xs text-slate-500">{p.parish}</p>}
                    </div>
                    {p.deal_grade && (
                      <span
                        className="text-xs font-bold px-2.5 py-1 rounded-md text-white"
                        style={{ backgroundColor: gradeColor }}
                      >
                        {p.deal_grade}
                        {p.deal_score != null && ` (${p.deal_score})`}
                      </span>
                    )}
                  </div>

                  {/* Specs line */}
                  <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
                    {oppLabel && (
                      <span className="bg-slate-100 px-2 py-0.5 rounded">{oppLabel}</span>
                    )}
                    {p.property_type && (
                      <span className="bg-slate-100 px-2 py-0.5 rounded">{p.property_type}</span>
                    )}
                    {p.area_m2 && (
                      <span className="bg-slate-100 px-2 py-0.5 rounded">{p.area_m2} m2</span>
                    )}
                    {p.typology && (
                      <span className="bg-slate-100 px-2 py-0.5 rounded">{p.typology}</span>
                    )}
                    {p.confidence != null && (
                      <span className="bg-slate-100 px-2 py-0.5 rounded">
                        Conf. {(p.confidence * 100).toFixed(0)}%
                      </span>
                    )}
                    {p.price_per_m2 != null && (
                      <span className="bg-slate-100 px-2 py-0.5 rounded">
                        {formatEUR(p.price_per_m2)}/m2
                      </span>
                    )}
                  </div>

                  {/* Price */}
                  <div className="mt-4">
                    <p className="text-lg font-bold text-teal-700">{formatEUR(p.asking_price)}</p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {!loading && filtered.length === 0 && (
        <div className="text-center py-16 text-slate-400">
          <p className="text-lg">Sem propriedades</p>
          <p className="text-sm mt-1">Ajuste os filtros ou adicione propriedades via API</p>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <p className="text-xs text-slate-500 uppercase tracking-wider">{label}</p>
      <p className="text-2xl font-bold text-slate-900 mt-1">{value}</p>
      {sub && <p className="text-xs text-teal-600 mt-0.5">{sub}</p>}
    </div>
  );
}

function FormField({
  name,
  label,
  placeholder,
  type = "text",
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
        className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-500 focus:border-teal-500 outline-none"
      />
    </div>
  );
}
