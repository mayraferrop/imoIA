"use client";

import { useState, useEffect, useCallback } from "react";
import { apiGet, apiPost, apiDelete } from "@/lib/api";

// Categorias para agrupamento visual
const CATEGORY_LABELS: Record<string, string> = {
  preco: "Preco",
  urgencia: "Urgencia",
  condicao: "Condicao do Imovel",
  mercado: "Posicao de Mercado",
  yield: "Yield / Rentabilidade",
  legal: "Legal / Judicial",
  outro: "Outro",
};

interface Signal {
  id: string;
  signal_text: string;
  signal_category: string;
  is_positive: boolean;
  priority: number;
  is_ai_suggested: boolean;
}

interface Strategy {
  id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  signals: Signal[];
}

// ---------------------------------------------------------------------------
// Componente principal
// ---------------------------------------------------------------------------

export default function StrategyPage() {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(false);

  // Step 1
  const [description, setDescription] = useState("");

  // Step 2
  const [signals, setSignals] = useState<Signal[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");

  // Step 3
  const [strategyName, setStrategyName] = useState("");
  const [saving, setSaving] = useState(false);

  // Editar estrategia existente
  const [editingStrategy, setEditingStrategy] = useState<Strategy | null>(null);

  const fetchStrategies = useCallback(async () => {
    const data = await apiGet<Strategy[]>("/api/v1/strategies");
    if (data) setStrategies(data);
  }, []);

  useEffect(() => {
    fetchStrategies();
  }, [fetchStrategies]);

  // Step 1: Gerar sinais com IA
  const handleSuggest = async () => {
    if (description.trim().length < 10) return;
    setLoading(true);
    try {
      const data = await apiPost<{ signals: Signal[] }>("/api/v1/strategies/suggest-signals", { description });
      if (!data) throw new Error("Erro ao gerar sinais");
      setSignals(data.signals || []);
      setStep(2);
    } catch (err) {
      alert("Erro ao gerar sinais com IA. Tente novamente.");
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Editar sinais
  const togglePositive = (id: string) => {
    setSignals((prev) =>
      prev.map((s) => (s.id === id ? { ...s, is_positive: !s.is_positive } : s))
    );
  };

  const removeSignal = (id: string) => {
    setSignals((prev) => prev.filter((s) => s.id !== id));
  };

  const startEdit = (s: Signal) => {
    setEditingId(s.id);
    setEditText(s.signal_text);
  };

  const saveEdit = () => {
    if (!editingId) return;
    setSignals((prev) =>
      prev.map((s) =>
        s.id === editingId ? { ...s, signal_text: editText } : s
      )
    );
    setEditingId(null);
    setEditText("");
  };

  const addManualSignal = () => {
    const id = crypto.randomUUID();
    setSignals((prev) => [
      ...prev,
      {
        id,
        signal_text: "",
        signal_category: "outro",
        is_positive: true,
        priority: prev.length + 1,
        is_ai_suggested: false,
      },
    ]);
    setEditingId(id);
    setEditText("");
  };

  // Step 3: Guardar estrategia
  const handleSave = async () => {
    if (!strategyName.trim()) return;
    setSaving(true);
    try {
      const result = await apiPost("/api/v1/strategies", {
        name: strategyName,
        description,
        is_active: true,
        signals: signals.map((s) => ({
          id: s.id,
          signal_text: s.signal_text,
          signal_category: s.signal_category,
          is_positive: s.is_positive,
          priority: s.priority,
          is_ai_suggested: s.is_ai_suggested,
        })),
      });
      if (!result) throw new Error("Erro ao guardar");
      await fetchStrategies();
      // Reset
      setStep(1);
      setDescription("");
      setSignals([]);
      setStrategyName("");
    } catch {
      alert("Erro ao guardar estrategia.");
    } finally {
      setSaving(false);
    }
  };

  const activateStrategy = async (id: string) => {
    await apiPost(`/api/v1/strategies/${id}/activate`);
    await fetchStrategies();
  };

  const deleteStrategy = async (id: string) => {
    if (!confirm("Tem a certeza que deseja remover esta estrategia?")) return;
    await apiDelete(`/api/v1/strategies/${id}`);
    await fetchStrategies();
  };

  const loadStrategyForEdit = (s: Strategy) => {
    setEditingStrategy(s);
    setDescription(s.description || "");
    setSignals(s.signals);
    setStrategyName(s.name);
    setStep(2);
  };

  // Agrupar sinais por tipo (positivo/negativo)
  const positiveSignals = signals.filter((s) => s.is_positive);
  const negativeSignals = signals.filter((s) => !s.is_positive);

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">
          Estrategia de Investimento
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Defina os criterios que a IA usa para encontrar oportunidades nos
          grupos de WhatsApp
        </p>
      </div>

      {/* Wizard Steps Indicator */}
      <div className="flex items-center gap-2 text-sm">
        {[1, 2, 3].map((n) => (
          <div key={n} className="flex items-center gap-2">
            <span
              className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                step === n
                  ? "bg-teal-600 text-white"
                  : step > n
                  ? "bg-teal-100 text-teal-700"
                  : "bg-slate-100 text-slate-400"
              }`}
            >
              {step > n ? "\u2713" : n}
            </span>
            <span
              className={
                step === n ? "text-teal-700 font-medium" : "text-slate-400"
              }
            >
              {n === 1
                ? "Descrever"
                : n === 2
                ? "Revisar Sinais"
                : "Guardar"}
            </span>
            {n < 3 && (
              <span className="mx-2 w-8 h-px bg-slate-200 inline-block" />
            )}
          </div>
        ))}
      </div>

      {/* STEP 1 — Descrever estrategia */}
      {step === 1 && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
          <h2 className="text-lg font-semibold text-slate-700">
            Descreva a sua estrategia
          </h2>
          <p className="text-sm text-slate-500">
            Escreva em linguagem natural o que procura. A IA vai sugerir sinais
            de classificacao com base na sua descricao.
          </p>
          <textarea
            className="w-full border border-slate-300 rounded-lg p-4 text-sm min-h-[120px] focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
            placeholder='Ex: "Procuro oportunidades de fix and flip em Lisboa e Porto, apartamentos T2/T3 ate 200k que precisem de obras, preferencialmente vendas urgentes ou abaixo do mercado"'
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <button
            onClick={handleSuggest}
            disabled={loading || description.trim().length < 10}
            className="bg-teal-600 text-white px-6 py-2.5 rounded-lg text-sm font-medium hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? "A gerar sinais com IA..." : "Gerar Sinais com IA"}
          </button>
        </div>
      )}

      {/* STEP 2 — Revisar e editar sinais */}
      {step === 2 && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-700">
                Sinais de Oportunidade ({positiveSignals.length})
              </h2>
              <span className="text-xs bg-green-50 text-green-700 px-2 py-1 rounded-full">
                A IA vai PROCURAR estes sinais
              </span>
            </div>
            <div className="space-y-2">
              {positiveSignals.map((s) => (
                <SignalCard
                  key={s.id}
                  signal={s}
                  editing={editingId === s.id}
                  editText={editText}
                  onEditTextChange={setEditText}
                  onStartEdit={() => startEdit(s)}
                  onSaveEdit={saveEdit}
                  onCancelEdit={() => setEditingId(null)}
                  onToggle={() => togglePositive(s.id)}
                  onRemove={() => removeSignal(s.id)}
                />
              ))}
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-700">
                Sinais a Ignorar ({negativeSignals.length})
              </h2>
              <span className="text-xs bg-red-50 text-red-700 px-2 py-1 rounded-full">
                A IA vai IGNORAR estes sinais
              </span>
            </div>
            <div className="space-y-2">
              {negativeSignals.map((s) => (
                <SignalCard
                  key={s.id}
                  signal={s}
                  editing={editingId === s.id}
                  editText={editText}
                  onEditTextChange={setEditText}
                  onStartEdit={() => startEdit(s)}
                  onSaveEdit={saveEdit}
                  onCancelEdit={() => setEditingId(null)}
                  onToggle={() => togglePositive(s.id)}
                  onRemove={() => removeSignal(s.id)}
                />
              ))}
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={addManualSignal}
              className="border border-slate-300 text-slate-600 px-4 py-2 rounded-lg text-sm hover:bg-slate-50 transition-colors"
            >
              + Adicionar sinal manual
            </button>
            <div className="flex-1" />
            <button
              onClick={() => setStep(1)}
              className="text-slate-500 px-4 py-2 text-sm hover:text-slate-700"
            >
              Voltar
            </button>
            <button
              onClick={() => setStep(3)}
              disabled={signals.length === 0}
              className="bg-teal-600 text-white px-6 py-2.5 rounded-lg text-sm font-medium hover:bg-teal-700 disabled:opacity-50 transition-colors"
            >
              Continuar
            </button>
          </div>
        </div>
      )}

      {/* STEP 3 — Guardar */}
      {step === 3 && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
          <h2 className="text-lg font-semibold text-slate-700">
            Guardar Estrategia
          </h2>
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">
              Nome da estrategia
            </label>
            <input
              type="text"
              className="w-full border border-slate-300 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
              placeholder='Ex: "Fix and Flip Lisboa"'
              value={strategyName}
              onChange={(e) => setStrategyName(e.target.value)}
            />
          </div>
          <div className="bg-slate-50 rounded-lg p-4 text-sm text-slate-600 space-y-1">
            <p>
              <strong>{positiveSignals.length}</strong> sinais a procurar
            </p>
            <p>
              <strong>{negativeSignals.length}</strong> sinais a ignorar
            </p>
            <p className="text-xs text-slate-400 mt-2">
              Esta estrategia sera ativada automaticamente e usada no proximo
              pipeline.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setStep(2)}
              className="text-slate-500 px-4 py-2 text-sm hover:text-slate-700"
            >
              Voltar
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !strategyName.trim()}
              className="bg-teal-600 text-white px-6 py-2.5 rounded-lg text-sm font-medium hover:bg-teal-700 disabled:opacity-50 transition-colors"
            >
              {saving ? "A guardar..." : "Guardar e Ativar"}
            </button>
          </div>
        </div>
      )}

      {/* Lista de estrategias existentes */}
      {strategies.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-slate-700">
            Estrategias Existentes
          </h2>
          {strategies.map((s) => (
            <div
              key={s.id}
              className={`bg-white rounded-xl border p-5 ${
                s.is_active
                  ? "border-teal-300 ring-1 ring-teal-100"
                  : "border-slate-200"
              }`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold text-slate-800">{s.name}</h3>
                    {s.is_active && (
                      <span className="text-xs bg-teal-50 text-teal-700 px-2 py-0.5 rounded-full font-medium">
                        Ativa
                      </span>
                    )}
                  </div>
                  {s.description && (
                    <p className="text-sm text-slate-500 mt-1 line-clamp-2">
                      {s.description}
                    </p>
                  )}
                  <p className="text-xs text-slate-400 mt-2">
                    {s.signals.filter((sig) => sig.is_positive).length} sinais
                    positivos,{" "}
                    {s.signals.filter((sig) => !sig.is_positive).length}{" "}
                    negativos
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {!s.is_active && (
                    <button
                      onClick={() => activateStrategy(s.id)}
                      className="text-xs bg-teal-50 text-teal-700 px-3 py-1.5 rounded-lg hover:bg-teal-100 transition-colors"
                    >
                      Ativar
                    </button>
                  )}
                  <button
                    onClick={() => loadStrategyForEdit(s)}
                    className="text-xs bg-slate-50 text-slate-600 px-3 py-1.5 rounded-lg hover:bg-slate-100 transition-colors"
                  >
                    Editar
                  </button>
                  <button
                    onClick={() => deleteStrategy(s.id)}
                    className="text-xs text-red-500 px-3 py-1.5 rounded-lg hover:bg-red-50 transition-colors"
                  >
                    Remover
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Signal Card component
// ---------------------------------------------------------------------------

function SignalCard({
  signal,
  editing,
  editText,
  onEditTextChange,
  onStartEdit,
  onSaveEdit,
  onCancelEdit,
  onToggle,
  onRemove,
}: {
  signal: Signal;
  editing: boolean;
  editText: string;
  onEditTextChange: (v: string) => void;
  onStartEdit: () => void;
  onSaveEdit: () => void;
  onCancelEdit: () => void;
  onToggle: () => void;
  onRemove: () => void;
}) {
  const categoryLabel =
    CATEGORY_LABELS[signal.signal_category] || signal.signal_category;

  if (editing) {
    return (
      <div className="flex items-center gap-2 p-3 bg-teal-50 rounded-lg border border-teal-200">
        <input
          type="text"
          className="flex-1 border border-slate-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
          value={editText}
          onChange={(e) => onEditTextChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") onSaveEdit();
            if (e.key === "Escape") onCancelEdit();
          }}
          autoFocus
        />
        <select
          className="border border-slate-300 rounded px-2 py-1.5 text-xs"
          value={signal.signal_category}
          disabled
        >
          {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <button
          onClick={onSaveEdit}
          className="text-teal-600 text-xs font-medium hover:text-teal-800"
        >
          Guardar
        </button>
        <button
          onClick={onCancelEdit}
          className="text-slate-400 text-xs hover:text-slate-600"
        >
          Cancelar
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 p-3 bg-slate-50 rounded-lg group hover:bg-slate-100 transition-colors">
      <span
        className={`w-2 h-2 rounded-full flex-shrink-0 ${
          signal.is_positive ? "bg-green-500" : "bg-red-400"
        }`}
      />
      <span className="flex-1 text-sm text-slate-700">
        {signal.signal_text}
      </span>
      <span className="text-xs text-slate-400 bg-white px-2 py-0.5 rounded">
        {categoryLabel}
      </span>
      {signal.is_ai_suggested && (
        <span className="text-xs text-purple-500 bg-purple-50 px-1.5 py-0.5 rounded">
          IA
        </span>
      )}
      <div className="hidden group-hover:flex items-center gap-1">
        <button
          onClick={onToggle}
          className="text-xs text-slate-400 hover:text-slate-600 px-1"
          title={
            signal.is_positive ? "Mover para ignorar" : "Mover para procurar"
          }
        >
          {signal.is_positive ? "\u2193" : "\u2191"}
        </button>
        <button
          onClick={onStartEdit}
          className="text-xs text-slate-400 hover:text-blue-600 px-1"
          title="Editar"
        >
          Editar
        </button>
        <button
          onClick={onRemove}
          className="text-xs text-slate-400 hover:text-red-500 px-1"
          title="Remover"
        >
          x
        </button>
      </div>
    </div>
  );
}
