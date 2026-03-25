import { apiGet } from "@/lib/api";
import { formatEUR, GRADE_COLORS } from "@/lib/utils";
import type { KanbanData } from "@/types/api";

const STATE_LABELS: Record<string, string> = {
  lead: "Lead",
  analysis: "Analise",
  proposal: "Proposta",
  negotiation: "Negociacao",
  cpcv: "CPCV",
  due_diligence: "Due Diligence",
  renovation: "Obra",
  marketing: "Marketing",
  closing: "Fecho",
  completed: "Concluido",
  discarded: "Descartado",
};

export const dynamic = "force-dynamic";

export default async function PipelinePage() {
  const kanban = await apiGet<KanbanData>("/api/v1/deals/kanban");
  const columns = kanban?.columns ?? {};
  const entries = Object.entries(columns);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">
          M4 — Deal Pipeline
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          {kanban?.total_deals ?? 0} deals no pipeline
        </p>
      </div>

      <div className="flex gap-4 overflow-x-auto pb-4">
        {entries.map(([state, col]) => (
          <div
            key={state}
            className="min-w-[280px] bg-slate-100 rounded-xl p-3 flex-shrink-0"
          >
            <div className="flex items-center justify-between mb-3 px-1">
              <h3 className="text-sm font-semibold text-slate-700">
                {STATE_LABELS[state] ?? state}
              </h3>
              <div className="flex items-center gap-2">
                <span className="text-xs bg-white px-2 py-0.5 rounded text-slate-500">
                  {col.count}
                </span>
                <span className="text-xs text-teal-700 font-medium">
                  {formatEUR(col.total_value)}
                </span>
              </div>
            </div>

            <div className="space-y-2">
              {col.deals.map((deal) => (
                <div
                  key={deal.id}
                  className="bg-white rounded-lg p-3 border border-slate-200 shadow-sm"
                >
                  <p className="text-sm font-medium text-slate-900">
                    {deal.property?.municipality ?? "Sem localizacao"}
                  </p>
                  <div className="flex items-center justify-between mt-2">
                    <span className="text-xs text-slate-500">
                      {deal.strategy}
                    </span>
                    <span className="text-sm font-semibold text-teal-700">
                      {formatEUR(deal.asking_price)}
                    </span>
                  </div>
                </div>
              ))}
              {col.deals.length === 0 && (
                <p className="text-xs text-slate-400 text-center py-4">
                  Sem deals
                </p>
              )}
            </div>
          </div>
        ))}
      </div>

      {Object.keys(columns).length === 0 && (
        <div className="text-center py-16 text-slate-400">
          <p className="text-lg">Pipeline vazio</p>
          <p className="text-sm mt-1">Crie deals a partir de propriedades</p>
        </div>
      )}
    </div>
  );
}
