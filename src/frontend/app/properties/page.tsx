import { apiGet } from "@/lib/api";
import { formatEUR, GRADE_COLORS } from "@/lib/utils";
import type { PropertiesResponse } from "@/types/api";
import Link from "next/link";

export const dynamic = "force-dynamic";

export default async function PropertiesPage() {
  const data = await apiGet<PropertiesResponse>("/api/v1/properties/?limit=50");
  const properties = data?.items ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">
          M1 — Propriedades
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          {data?.total ?? 0} propriedades no sistema
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {properties.map((p) => (
          <div
            key={p.id}
            className="bg-white rounded-xl border border-slate-200 overflow-hidden hover:shadow-md transition-shadow"
            style={{
              borderLeftWidth: 4,
              borderLeftColor:
                GRADE_COLORS[p.deal_grade ?? "D"] ?? GRADE_COLORS.D,
            }}
          >
            <div className="p-5">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-slate-900">
                    {p.municipality}
                  </h3>
                  {p.parish && (
                    <p className="text-xs text-slate-500">{p.parish}</p>
                  )}
                </div>
                {p.deal_grade && (
                  <span
                    className="text-xs font-bold px-2 py-1 rounded"
                    style={{
                      backgroundColor: `${GRADE_COLORS[p.deal_grade] ?? GRADE_COLORS.D}15`,
                      color: GRADE_COLORS[p.deal_grade] ?? GRADE_COLORS.D,
                    }}
                  >
                    {p.deal_grade}
                  </span>
                )}
              </div>

              <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
                {p.property_type && (
                  <span className="bg-slate-100 px-2 py-0.5 rounded">
                    {p.property_type}
                  </span>
                )}
                {p.typology && (
                  <span className="bg-slate-100 px-2 py-0.5 rounded">
                    {p.typology}
                  </span>
                )}
                {p.area_m2 && (
                  <span className="bg-slate-100 px-2 py-0.5 rounded">
                    {p.area_m2} m2
                  </span>
                )}
              </div>

              <div className="mt-4 flex items-center justify-between">
                <p className="text-lg font-bold text-teal-700">
                  {formatEUR(p.asking_price)}
                </p>
                {p.price_per_m2 && (
                  <p className="text-xs text-slate-400">
                    {formatEUR(p.price_per_m2)}/m2
                  </p>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {properties.length === 0 && (
        <div className="text-center py-16 text-slate-400">
          <p className="text-lg">Sem propriedades</p>
          <p className="text-sm mt-1">
            As propriedades aparecem aqui quando adicionadas via API
          </p>
        </div>
      )}
    </div>
  );
}
