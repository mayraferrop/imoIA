import { apiGet } from "@/lib/api";
import { formatEUR } from "@/lib/utils";
import type { PropertiesResponse, HealthResponse } from "@/types/api";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const [health, properties, dealStats] = await Promise.all([
    apiGet<HealthResponse>("/health"),
    apiGet<PropertiesResponse>("/api/v1/properties/?limit=5"),
    apiGet<any>("/api/v1/deals/stats"),
  ]);

  const apiOnline = health?.status === "ok";

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">
            Visao geral do portfolio
          </p>
        </div>
        <span
          className={`px-3 py-1 rounded-full text-xs font-medium ${
            apiOnline
              ? "bg-teal-50 text-teal-700"
              : "bg-red-50 text-red-700"
          }`}
        >
          API {apiOnline ? "activa" : "offline"}
        </span>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <KPICard
          label="Propriedades"
          value={String(properties?.total ?? 0)}
        />
        <KPICard
          label="Deals Activos"
          value={String(dealStats?.total_active ?? 0)}
        />
        <KPICard
          label="Valor Pipeline"
          value={formatEUR(dealStats?.total_pipeline_value ?? 0)}
        />
        <KPICard
          label="Deals Concluidos"
          value={String(dealStats?.total_completed ?? 0)}
        />
      </div>

      {/* Recent Properties */}
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">
          Propriedades Recentes
        </h2>
        {properties?.items?.length ? (
          <div className="space-y-3">
            {properties.items.map((p) => (
              <div
                key={p.id}
                className="flex items-center justify-between py-3 border-b border-slate-100 last:border-0"
              >
                <div>
                  <p className="text-sm font-medium text-slate-900">
                    {p.municipality}
                    {p.parish ? ` — ${p.parish}` : ""}
                  </p>
                  <p className="text-xs text-slate-500">
                    {p.property_type} {p.typology ? `| ${p.typology}` : ""}{" "}
                    {p.area_m2 ? `| ${p.area_m2}m2` : ""}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold text-teal-700">
                    {formatEUR(p.asking_price)}
                  </p>
                  {p.deal_grade && (
                    <span className="text-xs font-medium px-2 py-0.5 rounded bg-slate-100">
                      {p.deal_grade}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-400">Sem propriedades</p>
        )}
      </div>
    </div>
  );
}

function KPICard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
        {label}
      </p>
      <p className="text-2xl font-bold text-slate-900 mt-1">{value}</p>
    </div>
  );
}
