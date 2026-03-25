"use client";

import { useState, useEffect, useCallback } from "react";
import { fetcher } from "@/lib/api";
import { formatEUR, cn } from "@/lib/utils";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://imoia.onrender.com";

interface BrandKit {
  brand_name?: string;
  tagline?: string;
  website_url?: string;
  color_primary?: string;
  color_secondary?: string;
  color_accent?: string;
  font_heading?: string;
  font_body?: string;
  voice_tone?: string;
  voice_description?: string;
  voice_forbidden_words?: string[];
  contact_phone?: string;
  contact_email?: string;
  contact_whatsapp?: string;
  active_languages?: string[];
  logo_primary_url?: string;
  logo_white_url?: string;
  logo_icon_url?: string;
}

interface Listing {
  id: string;
  title_pt?: string;
  listing_type?: string;
  listing_price?: number;
  status?: string;
  slug?: string;
  short_description_pt?: string;
  description_pt?: string;
  highlights?: string[];
  content_whatsapp?: string;
  content_instagram_post?: string;
  content_facebook_post?: string;
  content_linkedin?: string;
  content_portal?: string;
  content_email_subject?: string;
  meta_title?: string;
  meta_description?: string;
  notes?: string;
  photos?: { url: string; is_cover?: boolean }[];
  cover_photo_url?: string;
}

interface Creative {
  id: string;
  creative_type?: string;
  format?: string;
  width?: number;
  height?: number;
  document_id?: string;
}

interface MktStats {
  active_listings?: number;
  total_value?: number;
  total_views?: number;
  total_contacts?: number;
  avg_days_on_market?: number;
}

const FONTS = ["Montserrat", "Inter", "Poppins", "Roboto", "Open Sans", "Lato", "Playfair Display", "Merriweather"];
const TONES = ["profissional", "luxo", "casual", "tecnico"];
const ALL_LANGS: Record<string, string> = {
  "pt-PT": "Portugues (PT)",
  "pt-BR": "Portugues (BR)",
  en: "English",
  fr: "Francais",
  zh: "Zhongwen",
};

const STATUS_COLORS: Record<string, string> = {
  draft: "#94A3B8",
  active: "#16A34A",
  paused: "#D97706",
  sold: "#7C3AED",
  archived: "#64748B",
};

export default function MarketingPage() {
  const [brandKit, setBrandKit] = useState<BrandKit | null>(null);
  const [showBkForm, setShowBkForm] = useState(false);
  const [listings, setListings] = useState<Listing[]>([]);
  const [stats, setStats] = useState<MktStats | null>(null);
  const [expandedListing, setExpandedListing] = useState<string | null>(null);
  const [listingCreatives, setListingCreatives] = useState<Record<string, Creative[]>>({});
  const [activeTab, setActiveTab] = useState<"marca" | "publicacoes">("marca");
  const [loading, setLoading] = useState(true);

  // Brand kit form state
  const [bkName, setBkName] = useState("");
  const [bkTagline, setBkTagline] = useState("");
  const [bkWebsite, setBkWebsite] = useState("");
  const [bkPrimary, setBkPrimary] = useState("#1E3A5F");
  const [bkSecondary, setBkSecondary] = useState("#F4A261");
  const [bkAccent, setBkAccent] = useState("#E76F51");
  const [bkFontH, setBkFontH] = useState("Montserrat");
  const [bkFontB, setBkFontB] = useState("Inter");
  const [bkTone, setBkTone] = useState("profissional");
  const [bkVoiceDesc, setBkVoiceDesc] = useState("");
  const [bkForbidden, setBkForbidden] = useState("");
  const [bkPhone, setBkPhone] = useState("");
  const [bkEmail, setBkEmail] = useState("");
  const [bkWhatsapp, setBkWhatsapp] = useState("");
  const [bkLangs, setBkLangs] = useState<string[]>(["pt-PT"]);

  // Create listing form
  const [showCreate, setShowCreate] = useState(false);
  const [createDealId, setCreateDealId] = useState("");
  const [createType, setCreateType] = useState("venda");
  const [createPrice, setCreatePrice] = useState(0);
  const [createTitle, setCreateTitle] = useState("");
  const [deals, setDeals] = useState<{ id: string; title: string; status: string }[]>([]);

  const loadData = useCallback(async () => {
    setLoading(true);
    const [bk, listingsData, mktStats] = await Promise.all([
      fetcher("/api/v1/marketing/brand-kit"),
      fetcher("/api/v1/marketing/listings?limit=100"),
      fetcher("/api/v1/marketing/stats"),
    ]);
    setBrandKit(bk);
    setListings(listingsData?.items ?? []);
    setStats(mktStats);
    if (!bk?.brand_name) setShowBkForm(true);
    setLoading(false);
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const populateBkForm = useCallback((bk: BrandKit | null) => {
    setBkName(bk?.brand_name ?? "");
    setBkTagline(bk?.tagline ?? "");
    setBkWebsite(bk?.website_url ?? "");
    setBkPrimary(bk?.color_primary ?? "#1E3A5F");
    setBkSecondary(bk?.color_secondary ?? "#F4A261");
    setBkAccent(bk?.color_accent ?? "#E76F51");
    setBkFontH(bk?.font_heading ?? "Montserrat");
    setBkFontB(bk?.font_body ?? "Inter");
    setBkTone(bk?.voice_tone ?? "profissional");
    setBkVoiceDesc(bk?.voice_description ?? "");
    setBkForbidden(bk?.voice_forbidden_words?.join(", ") ?? "");
    setBkPhone(bk?.contact_phone ?? "");
    setBkEmail(bk?.contact_email ?? "");
    setBkWhatsapp(bk?.contact_whatsapp ?? "");
    setBkLangs(bk?.active_languages ?? ["pt-PT"]);
  }, []);

  async function saveBrandKit() {
    if (!bkName) return;
    const forbidden = bkForbidden.split(",").map((w) => w.trim()).filter(Boolean);
    await fetch(`${API_BASE}/api/v1/marketing/brand-kit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        brand_name: bkName,
        tagline: bkTagline,
        website_url: bkWebsite,
        color_primary: bkPrimary,
        color_secondary: bkSecondary,
        color_accent: bkAccent,
        font_heading: bkFontH,
        font_body: bkFontB,
        voice_tone: bkTone,
        voice_description: bkVoiceDesc,
        voice_forbidden_words: forbidden,
        contact_phone: bkPhone,
        contact_email: bkEmail,
        contact_whatsapp: bkWhatsapp,
        active_languages: bkLangs.length > 0 ? bkLangs : ["pt-PT"],
      }),
    });
    setShowBkForm(false);
    loadData();
  }

  async function loadCreatives(listingId: string) {
    const data = await fetcher(`/api/v1/marketing/listings/${listingId}/creatives`);
    setListingCreatives((prev) => ({ ...prev, [listingId]: data ?? [] }));
  }

  async function generateCreatives(listingId: string) {
    await fetch(`${API_BASE}/api/v1/marketing/listings/${listingId}/creatives/generate-all`, {
      method: "POST",
    });
    loadCreatives(listingId);
  }

  async function createListing() {
    if (!createDealId || createPrice <= 0) return;
    const res = await fetch(`${API_BASE}/api/v1/marketing/deals/${createDealId}/listing`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ listing_type: createType, listing_price: createPrice, auto_generate: false }),
    });
    if (res.ok) {
      const result = await res.json();
      if (createTitle && result?.id) {
        await fetch(`${API_BASE}/api/v1/marketing/listings/${result.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title_pt: createTitle }),
        });
      }
      setShowCreate(false);
      loadData();
    }
  }

  async function loadDeals() {
    const data = await fetcher("/api/v1/deals/?limit=100");
    if (data?.items) {
      setDeals(data.items.map((d: any) => ({ id: d.id, title: d.title ?? d.id.slice(0, 8), status: d.status })));
      if (data.items.length > 0) setCreateDealId(data.items[0].id);
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-slate-900">M7 — Marketing</h1>
        <div className="text-center py-16 text-slate-400">A carregar...</div>
      </div>
    );
  }

  const hasBrandKit = brandKit?.brand_name;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">M7 — Marketing Engine</h1>
        <p className="text-sm text-slate-500 mt-1">Gestao de marca, publicacoes e conteudo</p>
      </div>

      {/* Tabs */}
      {hasBrandKit && (
        <div className="flex gap-1 border-b border-slate-200">
          <button
            onClick={() => setActiveTab("marca")}
            className={cn(
              "px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors",
              activeTab === "marca"
                ? "border-teal-700 text-teal-700"
                : "border-transparent text-slate-500 hover:text-slate-700"
            )}
          >
            Marca
          </button>
          <button
            onClick={() => setActiveTab("publicacoes")}
            className={cn(
              "px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors",
              activeTab === "publicacoes"
                ? "border-teal-700 text-teal-700"
                : "border-transparent text-slate-500 hover:text-slate-700"
            )}
          >
            Publicacoes
          </button>
        </div>
      )}

      {/* TAB MARCA */}
      {(activeTab === "marca" || !hasBrandKit) && (
        <div className="space-y-6">
          {!hasBrandKit && !showBkForm && (
            <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
              <h2 className="text-lg font-semibold text-slate-900">Configure a sua marca para comecar</h2>
              <p className="text-sm text-slate-500 mt-1">O brand kit define cores, fontes e tom de voz para todo o conteudo gerado.</p>
              <button
                onClick={() => { populateBkForm(null); setShowBkForm(true); }}
                className="mt-4 px-4 py-2 bg-teal-700 text-white text-sm font-medium rounded-lg hover:bg-teal-800"
              >
                Configurar Brand Kit
              </button>
            </div>
          )}

          {hasBrandKit && !showBkForm && (
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <div className="flex items-start justify-between">
                <div className="space-y-2">
                  <h2 className="text-lg font-semibold text-slate-900">
                    {brandKit.brand_name} <span className="text-sm font-normal text-slate-500">— {brandKit.tagline}</span>
                  </h2>
                  <p className="text-sm text-slate-500">
                    {brandKit.website_url} | {brandKit.contact_phone} | {brandKit.contact_email}
                  </p>
                  <p className="text-sm text-slate-500">
                    Tom: {brandKit.voice_tone} | Idiomas: {brandKit.active_languages?.join(", ")} | Fontes: {brandKit.font_heading} / {brandKit.font_body}
                  </p>
                  <div className="flex gap-3 mt-2">
                    {[
                      { label: "primary", color: brandKit.color_primary },
                      { label: "secondary", color: brandKit.color_secondary },
                      { label: "accent", color: brandKit.color_accent },
                    ].map((c) => (
                      <div key={c.label} className="flex items-center gap-1.5">
                        <div
                          className="w-5 h-5 rounded border border-slate-200"
                          style={{ backgroundColor: c.color }}
                        />
                        <span className="text-xs text-slate-500">{c.label}: {c.color}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <button
                  onClick={() => { populateBkForm(brandKit); setShowBkForm(true); }}
                  className="px-3 py-1.5 text-sm font-medium text-teal-700 border border-teal-700 rounded-lg hover:bg-teal-50"
                >
                  Editar marca
                </button>
              </div>

              {/* Logos */}
              <div className="mt-6 pt-4 border-t border-slate-100">
                <h3 className="text-sm font-semibold text-slate-700 mb-3">Logos</h3>
                <div className="grid grid-cols-3 gap-4">
                  {[
                    { type: "primary", label: "Logo principal", field: "logo_primary_url" },
                    { type: "white", label: "Logo fundo escuro", field: "logo_white_url" },
                    { type: "icon", label: "Favicon", field: "logo_icon_url" },
                  ].map(({ type, label, field }) => {
                    const url = (brandKit as any)?.[field];
                    return (
                      <div key={type} className="text-center">
                        <p className="text-xs text-slate-500 mb-2">{label}</p>
                        {url ? (
                          <div className="bg-slate-50 rounded-lg p-4 border border-slate-100">
                            <img
                              src={url.startsWith("/") ? `${API_BASE}${url}` : url}
                              alt={label}
                              className="max-h-16 mx-auto object-contain"
                              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                            />
                            <p className="text-xs text-green-600 mt-2">Configurado</p>
                          </div>
                        ) : (
                          <div className="bg-slate-50 rounded-lg p-4 border border-dashed border-slate-300 text-xs text-slate-400">
                            Nao configurado
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* Brand Kit Form */}
          {showBkForm && (
            <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-6">
              <h2 className="text-lg font-semibold text-slate-900">
                {hasBrandKit ? "Editar Brand Kit" : "Configurar Brand Kit"}
              </h2>

              {/* Identidade */}
              <div>
                <h3 className="text-sm font-semibold text-slate-700 mb-3">Identidade</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">Nome da marca *</label>
                    <input
                      type="text"
                      value={bkName}
                      onChange={(e) => setBkName(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">Website</label>
                    <input
                      type="text"
                      value={bkWebsite}
                      onChange={(e) => setBkWebsite(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                    />
                  </div>
                </div>
                <div className="mt-3">
                  <label className="block text-xs text-slate-500 mb-1">Tagline</label>
                  <input
                    type="text"
                    value={bkTagline}
                    onChange={(e) => setBkTagline(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                  />
                </div>
              </div>

              {/* Cores */}
              <div>
                <h3 className="text-sm font-semibold text-slate-700 mb-3">Cores</h3>
                <div className="grid grid-cols-3 gap-4">
                  {[
                    { label: "Primaria", value: bkPrimary, set: setBkPrimary },
                    { label: "Secundaria", value: bkSecondary, set: setBkSecondary },
                    { label: "Destaque", value: bkAccent, set: setBkAccent },
                  ].map((c) => (
                    <div key={c.label}>
                      <label className="block text-xs text-slate-500 mb-1">{c.label}</label>
                      <div className="flex items-center gap-2">
                        <input
                          type="color"
                          value={c.value}
                          onChange={(e) => c.set(e.target.value)}
                          className="w-10 h-10 rounded border border-slate-200 cursor-pointer"
                        />
                        <input
                          type="text"
                          value={c.value}
                          onChange={(e) => c.set(e.target.value)}
                          className="flex-1 px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Fontes */}
              <div>
                <h3 className="text-sm font-semibold text-slate-700 mb-3">Fontes</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">Heading</label>
                    <select
                      value={bkFontH}
                      onChange={(e) => setBkFontH(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                    >
                      {FONTS.map((f) => <option key={f} value={f}>{f}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">Body</label>
                    <select
                      value={bkFontB}
                      onChange={(e) => setBkFontB(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                    >
                      {FONTS.map((f) => <option key={f} value={f}>{f}</option>)}
                    </select>
                  </div>
                </div>
              </div>

              {/* Tom de voz */}
              <div>
                <h3 className="text-sm font-semibold text-slate-700 mb-3">Tom de voz</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">Tom</label>
                    <select
                      value={bkTone}
                      onChange={(e) => setBkTone(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                    >
                      {TONES.map((t) => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">Palavras proibidas (virgula)</label>
                    <input
                      type="text"
                      value={bkForbidden}
                      onChange={(e) => setBkForbidden(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                    />
                  </div>
                </div>
                <div className="mt-3">
                  <label className="block text-xs text-slate-500 mb-1">Descricao do tom</label>
                  <textarea
                    value={bkVoiceDesc}
                    onChange={(e) => setBkVoiceDesc(e.target.value)}
                    rows={2}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                  />
                </div>
              </div>

              {/* Contacto */}
              <div>
                <h3 className="text-sm font-semibold text-slate-700 mb-3">Contacto</h3>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">Telefone</label>
                    <input type="text" value={bkPhone} onChange={(e) => setBkPhone(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">Email</label>
                    <input type="text" value={bkEmail} onChange={(e) => setBkEmail(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">WhatsApp</label>
                    <input type="text" value={bkWhatsapp} onChange={(e) => setBkWhatsapp(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500" />
                  </div>
                </div>
              </div>

              {/* Idiomas */}
              <div>
                <h3 className="text-sm font-semibold text-slate-700 mb-3">Idiomas activos</h3>
                <div className="flex gap-4 flex-wrap">
                  {Object.entries(ALL_LANGS).map(([code, label]) => (
                    <label key={code} className="flex items-center gap-2 text-sm text-slate-700">
                      <input
                        type="checkbox"
                        checked={bkLangs.includes(code)}
                        onChange={(e) => {
                          if (e.target.checked) setBkLangs((prev) => [...prev, code]);
                          else setBkLangs((prev) => prev.filter((l) => l !== code));
                        }}
                        className="rounded border-slate-300 text-teal-700 focus:ring-teal-500"
                      />
                      {label}
                    </label>
                  ))}
                </div>
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  onClick={saveBrandKit}
                  className="px-4 py-2 bg-teal-700 text-white text-sm font-medium rounded-lg hover:bg-teal-800"
                >
                  {hasBrandKit ? "Guardar Brand Kit" : "Guardar e comecar"}
                </button>
                {hasBrandKit && (
                  <button
                    onClick={() => setShowBkForm(false)}
                    className="px-4 py-2 text-sm font-medium text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50"
                  >
                    Cancelar
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB PUBLICACOES */}
      {activeTab === "publicacoes" && hasBrandKit && (
        <div className="space-y-6">
          {/* Stats */}
          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              {[
                { label: "Publicacoes", value: stats.active_listings ?? 0 },
                { label: "Valor total", value: formatEUR(stats.total_value) },
                { label: "Views", value: stats.total_views ?? 0 },
                { label: "Contactos", value: stats.total_contacts ?? 0 },
                { label: "DOM medio", value: `${(stats.avg_days_on_market ?? 0).toFixed(0)}d` },
              ].map((s) => (
                <div key={s.label} className="bg-white rounded-xl border border-slate-200 p-4">
                  <p className="text-xs text-slate-500">{s.label}</p>
                  <p className="text-xl font-bold text-slate-900 mt-1">{s.value}</p>
                </div>
              ))}
            </div>
          )}

          {/* Listings */}
          {listings.length === 0 ? (
            <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-slate-400">
              <p>Sem publicacoes.</p>
              <p className="text-sm mt-1">As publicacoes sao criadas automaticamente quando um deal avanca para &quot;Em Venda&quot;.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {listings.map((listing) => {
                const title = listing.title_pt || listing.notes || "Publicacao";
                const status = listing.status ?? "?";
                const statusColor = STATUS_COLORS[status] ?? "#94A3B8";
                const isExpanded = expandedListing === listing.id;

                return (
                  <div key={listing.id} className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                    <button
                      onClick={() => {
                        setExpandedListing(isExpanded ? null : listing.id);
                        if (!isExpanded && !listingCreatives[listing.id]) {
                          loadCreatives(listing.id);
                        }
                      }}
                      className="w-full px-5 py-4 flex items-center justify-between hover:bg-slate-50 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
                        <span className="text-sm font-medium text-teal-700">{formatEUR(listing.listing_price)}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span
                          className="text-xs font-medium px-2.5 py-1 rounded-full"
                          style={{ backgroundColor: `${statusColor}15`, color: statusColor }}
                        >
                          {status}
                        </span>
                        <svg
                          className={cn("w-4 h-4 text-slate-400 transition-transform", isExpanded && "rotate-180")}
                          fill="none" viewBox="0 0 24 24" stroke="currentColor"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                      </div>
                    </button>

                    {isExpanded && (
                      <div className="px-5 pb-5 border-t border-slate-100 pt-4 space-y-4">
                        {/* Info */}
                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-1 text-sm">
                            <p className="text-slate-500">Tipo: <span className="text-slate-900">{listing.listing_type ?? "N/A"}</span></p>
                            {listing.slug && <p className="text-slate-500">Slug: <code className="text-xs bg-slate-100 px-1 rounded">{listing.slug}</code></p>}
                          </div>
                          <div>
                            {listing.short_description_pt && (
                              <p className="text-sm text-slate-500">{listing.short_description_pt}</p>
                            )}
                            {listing.highlights && listing.highlights.length > 0 && (
                              <ul className="mt-1 text-xs text-slate-500 list-disc list-inside">
                                {listing.highlights.slice(0, 6).map((h, i) => <li key={i}>{h}</li>)}
                              </ul>
                            )}
                          </div>
                        </div>

                        {/* Content sections */}
                        <div className="space-y-3">
                          {listing.title_pt && (
                            <div>
                              <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Website</h4>
                              <p className="text-sm text-slate-700 font-medium">{listing.title_pt}</p>
                              {listing.description_pt && <p className="text-sm text-slate-500 mt-1 line-clamp-3">{listing.description_pt}</p>}
                            </div>
                          )}
                          {listing.content_whatsapp && (
                            <div>
                              <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">WhatsApp</h4>
                              <pre className="bg-slate-50 rounded-lg p-3 text-xs text-slate-700 whitespace-pre-wrap overflow-auto max-h-32">{listing.content_whatsapp}</pre>
                            </div>
                          )}
                          {listing.content_instagram_post && (
                            <div>
                              <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Instagram</h4>
                              <pre className="bg-slate-50 rounded-lg p-3 text-xs text-slate-700 whitespace-pre-wrap overflow-auto max-h-32">{listing.content_instagram_post}</pre>
                            </div>
                          )}
                          {listing.content_facebook_post && (
                            <div>
                              <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Facebook</h4>
                              <pre className="bg-slate-50 rounded-lg p-3 text-xs text-slate-700 whitespace-pre-wrap overflow-auto max-h-32">{listing.content_facebook_post}</pre>
                            </div>
                          )}
                          {listing.content_linkedin && (
                            <div>
                              <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">LinkedIn</h4>
                              <pre className="bg-slate-50 rounded-lg p-3 text-xs text-slate-700 whitespace-pre-wrap overflow-auto max-h-32">{listing.content_linkedin}</pre>
                            </div>
                          )}
                          {listing.content_portal && (
                            <div>
                              <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Portal (Idealista)</h4>
                              <pre className="bg-slate-50 rounded-lg p-3 text-xs text-slate-700 whitespace-pre-wrap overflow-auto max-h-32">{listing.content_portal}</pre>
                            </div>
                          )}
                          {listing.content_email_subject && (
                            <div>
                              <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Email</h4>
                              <p className="text-sm text-slate-700">Subject: <code className="text-xs bg-slate-100 px-1 rounded">{listing.content_email_subject}</code></p>
                            </div>
                          )}
                          {(listing.meta_title || listing.meta_description) && (
                            <div>
                              <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">SEO</h4>
                              {listing.meta_title && <p className="text-sm text-slate-700">Title: <code className="text-xs bg-slate-100 px-1 rounded">{listing.meta_title}</code></p>}
                              {listing.meta_description && <p className="text-xs text-slate-500 mt-1">{listing.meta_description}</p>}
                            </div>
                          )}
                        </div>

                        {/* Creatives */}
                        <div className="border-t border-slate-100 pt-4">
                          <div className="flex items-center justify-between mb-3">
                            <h4 className="text-sm font-semibold text-slate-700">Criativos</h4>
                            <button
                              onClick={() => generateCreatives(listing.id)}
                              className="text-xs font-medium text-teal-700 hover:text-teal-800"
                            >
                              {listingCreatives[listing.id]?.length ? "Regenerar" : "Gerar criativos"}
                            </button>
                          </div>
                          {listingCreatives[listing.id]?.length ? (
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                              {listingCreatives[listing.id].map((c) => (
                                <div key={c.id} className="bg-slate-50 rounded-lg p-3 border border-slate-100">
                                  <p className="text-sm font-medium text-slate-900">{c.creative_type}</p>
                                  <p className="text-xs text-slate-500">{c.width}x{c.height} {c.format}</p>
                                  {c.document_id && (
                                    <a
                                      href={`${API_BASE}/api/v1/documents/${c.document_id}/download`}
                                      className="text-xs text-teal-700 hover:text-teal-800 mt-1 inline-block"
                                      target="_blank"
                                      rel="noopener noreferrer"
                                    >
                                      Download
                                    </a>
                                  )}
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className="text-xs text-slate-400">Sem criativos gerados.</p>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Create listing */}
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <button
              onClick={() => {
                setShowCreate(!showCreate);
                if (!showCreate && deals.length === 0) loadDeals();
              }}
              className="w-full px-5 py-3 flex items-center justify-between hover:bg-slate-50 text-sm font-medium text-slate-600"
            >
              Criar publicacao manualmente
              <svg
                className={cn("w-4 h-4 text-slate-400 transition-transform", showCreate && "rotate-180")}
                fill="none" viewBox="0 0 24 24" stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {showCreate && (
              <div className="px-5 pb-5 border-t border-slate-100 pt-4 space-y-4">
                {deals.length === 0 ? (
                  <p className="text-sm text-slate-400">Nenhum deal encontrado. Crie um deal no M4 primeiro.</p>
                ) : (
                  <>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs text-slate-500 mb-1">Deal</label>
                        <select
                          value={createDealId}
                          onChange={(e) => setCreateDealId(e.target.value)}
                          className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                        >
                          {deals.map((d) => <option key={d.id} value={d.id}>{d.title} ({d.status})</option>)}
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs text-slate-500 mb-1">Tipo</label>
                        <select
                          value={createType}
                          onChange={(e) => setCreateType(e.target.value)}
                          className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                        >
                          <option value="venda">Venda</option>
                          <option value="arrendamento">Arrendamento</option>
                        </select>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs text-slate-500 mb-1">Preco (EUR)</label>
                        <input
                          type="number"
                          value={createPrice}
                          onChange={(e) => setCreatePrice(Number(e.target.value))}
                          className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-500 mb-1">Titulo</label>
                        <input
                          type="text"
                          value={createTitle}
                          onChange={(e) => setCreateTitle(e.target.value)}
                          className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                        />
                      </div>
                    </div>
                    <button
                      onClick={createListing}
                      className="px-4 py-2 bg-teal-700 text-white text-sm font-medium rounded-lg hover:bg-teal-800"
                    >
                      Criar
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
