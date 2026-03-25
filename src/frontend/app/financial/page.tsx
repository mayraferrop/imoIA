"use client";

import { useState } from "react";
import { formatEUR, formatPercent } from "@/lib/utils";
import type { FinancialSimulation } from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function FinancialPage() {
  const [result, setResult] = useState<FinancialSimulation | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSimulate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    const fd = new FormData(e.currentTarget);

    const body = {
      purchase_price: Number(fd.get("purchase_price")),
      renovation_cost: Number(fd.get("renovation_cost")),
      estimated_sale_price: Number(fd.get("estimated_sale_price")),
      holding_months: Number(fd.get("holding_months") || 6),
      municipality: (fd.get("municipality") as string) || "Lisboa",
      property_type: "secondary",
      country: "PT",
    };

    try {
      const res = await fetch(`${API_BASE}/api/v1/financial/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) setResult(await res.json());
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">
          M3 — Simulador Financeiro
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Simular investimento fix and flip
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Form */}
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-lg font-semibold mb-4">Parametros</h2>
          <form onSubmit={handleSimulate} className="space-y-4">
            <Field name="purchase_price" label="Preco de compra" placeholder="150000" />
            <Field name="renovation_cost" label="Custo de obra" placeholder="30000" />
            <Field name="estimated_sale_price" label="Preco de venda estimado" placeholder="250000" />
            <Field name="holding_months" label="Meses de detencao" placeholder="6" />
            <Field name="municipality" label="Concelho" placeholder="Lisboa" type="text" />
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
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold">Resultado</h2>
              <span
                className={`px-4 py-1.5 rounded-full text-sm font-bold ${
                  result.go_no_go === "GO"
                    ? "bg-green-100 text-green-700"
                    : result.go_no_go === "CAUTION"
                    ? "bg-amber-100 text-amber-700"
                    : "bg-red-100 text-red-700"
                }`}
              >
                {result.go_no_go}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <ResultCard label="Investimento Total" value={formatEUR(result.total_investment)} />
              <ResultCard label="Lucro Estimado" value={formatEUR(result.estimated_profit)} />
              <ResultCard label="ROI" value={formatPercent(result.roi_simple)} />
              <ResultCard label="MOIC" value={`${result.moic?.toFixed(2)}x`} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
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
      <label className="block text-sm font-medium text-slate-700 mb-1">
        {label}
      </label>
      <input
        name={name}
        type={type}
        placeholder={placeholder}
        className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-500 focus:border-teal-500 outline-none"
      />
    </div>
  );
}

function ResultCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-slate-50 rounded-lg p-4">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-xl font-bold text-slate-900 mt-1">{value}</p>
    </div>
  );
}
