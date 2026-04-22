"use client";

import { useState, useEffect, useCallback } from "react";
import useSWR, { mutate as globalMutate } from "swr";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiPost, apiUpload, apiDelete, API_BASE } from "@/lib/api";
import { formatEUR, cn } from "@/lib/utils";

const BRAND_KIT_KEY = "/api/v1/marketing/brand-kit";
const LISTINGS_KEY = "/api/v1/marketing/listings?limit=100";
const STATS_KEY = "/api/v1/marketing/stats";

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
  photos?: ListingPhoto[];
  cover_photo_url?: string;
}

interface ListingPhoto {
  document_id?: string;
  url: string;
  filename?: string;
  order?: number;
  is_cover?: boolean;
}

interface MktStats {
  active_listings?: number;
  total_value?: number;
  total_views?: number;
  total_contacts?: number;
  avg_days_on_market?: number;
}

const FONTS = ["Montserrat", "Inter", "Poppins", "Roboto", "Open Sans", "Lato", "Playfair Display", "Merriweather"];
const TONES = ["profissional", "luxo", "casual", "técnico"];
const ALL_LANGS: Record<string, string> = {
  "pt-PT": "Português (PT)",
  "pt-BR": "Português (BR)",
  en: "English",
  fr: "Français",
  zh: "Zhongwen",
};

// Backend pode retornar arrays JSON como string — parse seguro
function safeArray(val: unknown): string[] {
  if (Array.isArray(val)) return val;
  if (typeof val === "string") { try { const parsed = JSON.parse(val); if (Array.isArray(parsed)) return parsed; } catch {} }
  return [];
}

const STATUS_COLORS: Record<string, string> = {
  draft: "#94A3B8",
  active: "#16A34A",
  paused: "#D97706",
  sold: "#7C3AED",
  archived: "#64748B",
};

export default function MarketingPage() {
  const { data: brandKit } = useSWR<BrandKit | null>(BRAND_KIT_KEY);
  const { data: listingsData } = useSWR<{ items: Listing[] } | null>(LISTINGS_KEY);
  const { data: stats } = useSWR<MktStats | null>(STATS_KEY);
  const listings = listingsData?.items ?? [];
  const loading =
    brandKit === undefined || listingsData === undefined || stats === undefined;

  const [showBkForm, setShowBkForm] = useState(false);
  const [activeTab, setActiveTab] = useState<"marca" | "publicacoes">("marca");

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

  const loadData = useCallback(async () => {
    await Promise.all([
      globalMutate(BRAND_KIT_KEY),
      globalMutate(LISTINGS_KEY),
      globalMutate(STATS_KEY),
    ]);
  }, []);

  useEffect(() => {
    if (brandKit !== undefined && !brandKit?.brand_name) {
      setShowBkForm(true);
    }
  }, [brandKit]);

  // Seed SWR cache of individual listings from list response.
  // Makes navigation to /marketing/[id] instant — data already cached.
  useEffect(() => {
    if (!listings.length) return;
    for (const l of listings) {
      globalMutate(`/api/v1/marketing/listings/${l.id}`, l, { revalidate: false });
    }
  }, [listings]);

  const router = useRouter();
  const prefetchListing = useCallback((id: string) => {
    router.prefetch(`/marketing/${id}`);
    globalMutate(`/api/v1/marketing/listings/${id}`);
    globalMutate(`/api/v1/marketing/listings/${id}/creatives`);
  }, [router]);

  useEffect(() => {
    if (!listings.length) return;
    const t = setTimeout(() => {
      for (const l of listings) {
        router.prefetch(`/marketing/${l.id}`);
      }
    }, 100);
    return () => clearTimeout(t);
  }, [listings, router]);

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
    setBkForbidden(safeArray(bk?.voice_forbidden_words).join(", "));
    setBkPhone(bk?.contact_phone ?? "");
    setBkEmail(bk?.contact_email ?? "");
    setBkWhatsapp(bk?.contact_whatsapp ?? "");
    const langs = safeArray(bk?.active_languages);
    setBkLangs(langs.length > 0 ? langs : ["pt-PT"]);
  }, []);

  const [uploadingLogo, setUploadingLogo] = useState<Record<string, boolean>>({});

  async function uploadLogo(logoType: "primary" | "white" | "icon", file: File) {
    if (file.size > 2 * 1024 * 1024) {
      alert("Logo excede 2MB");
      return;
    }
    setUploadingLogo((p) => ({ ...p, [logoType]: true }));
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await apiUpload(`/api/v1/marketing/brand-kit/logo?logo_type=${logoType}`, fd);
      if (!res) {
        alert("Upload falhou");
        return;
      }
      await loadData();
    } finally {
      setUploadingLogo((p) => ({ ...p, [logoType]: false }));
    }
  }

  async function deleteLogo(logoType: "primary" | "white" | "icon") {
    if (!confirm("Remover este logo?")) return;
    setUploadingLogo((p) => ({ ...p, [logoType]: true }));
    try {
      await apiDelete(`/api/v1/marketing/brand-kit/logo?logo_type=${logoType}`);
      await loadData();
    } finally {
      setUploadingLogo((p) => ({ ...p, [logoType]: false }));
    }
  }

  async function saveBrandKit() {
    if (!bkName) return;
    const forbidden = bkForbidden.split(",").map((w) => w.trim()).filter(Boolean);
    await apiPost("/api/v1/marketing/brand-kit", {
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
    });
    setShowBkForm(false);
    loadData();
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
        <p className="text-sm text-slate-500 mt-1">Gestão de marca, publicações e conteúdo</p>
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
            Publicações
          </button>
        </div>
      )}

      {/* TAB MARCA */}
      {(activeTab === "marca" || !hasBrandKit) && (
        <div className="space-y-6">
          {!hasBrandKit && !showBkForm && (
            <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
              <h2 className="text-lg font-semibold text-slate-900">Configure a sua marca para começar</h2>
              <p className="text-sm text-slate-500 mt-1">O brand kit define cores, fontes e tom de voz para todo o conteúdo gerado.</p>
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
                    Tom: {brandKit.voice_tone} | Idiomas: {safeArray(brandKit.active_languages).join(", ")} | Fontes: {brandKit.font_heading} / {brandKit.font_body}
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
                            Não configurado
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
                    { label: "Primária", value: bkPrimary, set: setBkPrimary },
                    { label: "Secundária", value: bkSecondary, set: setBkSecondary },
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
                    <label className="block text-xs text-slate-500 mb-1">Palavras proibidas (vírgula)</label>
                    <input
                      type="text"
                      value={bkForbidden}
                      onChange={(e) => setBkForbidden(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                    />
                  </div>
                </div>
                <div className="mt-3">
                  <label className="block text-xs text-slate-500 mb-1">Descrição do tom</label>
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

              {hasBrandKit && (
                <div>
                  <h3 className="text-sm font-semibold text-slate-700 mb-3">Logos</h3>
                  <p className="text-xs text-slate-500 mb-3">
                    PNG, JPG, WebP ou SVG. Máximo 2MB por ficheiro.
                  </p>
                  <div className="grid grid-cols-3 gap-4">
                    {[
                      { type: "primary" as const, label: "Logo principal", field: "logo_primary_url", bg: "bg-slate-50" },
                      { type: "white" as const, label: "Logo fundo escuro", field: "logo_white_url", bg: "bg-slate-800" },
                      { type: "icon" as const, label: "Favicon", field: "logo_icon_url", bg: "bg-slate-50" },
                    ].map(({ type, label, field, bg }) => {
                      const url = (brandKit as any)?.[field];
                      const busy = uploadingLogo[type];
                      return (
                        <div key={type} className="space-y-2">
                          <p className="text-xs text-slate-500">{label}</p>
                          <div className={cn(
                            "rounded-lg p-4 border border-slate-100 flex items-center justify-center min-h-[80px]",
                            bg
                          )}>
                            {url ? (
                              <img
                                src={url.startsWith("/") ? `${API_BASE}${url}` : url}
                                alt={label}
                                className="max-h-12 object-contain"
                                onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                              />
                            ) : (
                              <span className="text-xs text-slate-400">Sem logo</span>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            <label className="flex-1 text-center px-2 py-1.5 text-xs font-medium text-teal-700 border border-teal-200 rounded-md hover:bg-teal-50 cursor-pointer">
                              {busy ? "..." : url ? "Substituir" : "Carregar"}
                              <input
                                type="file"
                                accept="image/png,image/jpeg,image/webp,image/svg+xml"
                                className="hidden"
                                disabled={busy}
                                onChange={(e) => {
                                  const f = e.target.files?.[0];
                                  if (f) uploadLogo(type, f);
                                  e.target.value = "";
                                }}
                              />
                            </label>
                            {url && (
                              <button
                                onClick={() => deleteLogo(type)}
                                disabled={busy}
                                className="px-2 py-1.5 text-xs font-medium text-red-600 border border-red-200 rounded-md hover:bg-red-50 disabled:opacity-50"
                              >
                                Remover
                              </button>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              <div className="flex gap-3 pt-2">
                <button
                  onClick={saveBrandKit}
                  className="px-4 py-2 bg-teal-700 text-white text-sm font-medium rounded-lg hover:bg-teal-800"
                >
                  {hasBrandKit ? "Guardar Brand Kit" : "Guardar e começar"}
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
                { label: "Publicações", value: stats.active_listings ?? 0 },
                { label: "Valor total", value: formatEUR(stats.total_value) },
                { label: "Views", value: stats.total_views ?? 0 },
                { label: "Contactos", value: stats.total_contacts ?? 0 },
                { label: "DOM médio", value: `${(stats.avg_days_on_market ?? 0).toFixed(0)}d` },
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
              <p>Sem publicações.</p>
              <p className="text-sm mt-1">As publicações são criadas automaticamente quando um deal avança para &quot;Em Venda&quot;.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {listings.map((listing) => {
                const title = listing.title_pt || listing.notes || "Publicação";
                const status = listing.status ?? "?";
                const statusColor = STATUS_COLORS[status] ?? "#94A3B8";
                const coverPhoto = listing.photos?.find(
                  (p) => p.is_cover || (!!listing.cover_photo_url && !!p.document_id && listing.cover_photo_url.includes(p.document_id))
                );
                const thumbUrl = coverPhoto?.url ?? listing.cover_photo_url;
                const photoCount = listing.photos?.length ?? 0;

                return (
                  <Link
                    key={listing.id}
                    href={`/marketing/${listing.id}`}
                    prefetch
                    onMouseEnter={() => prefetchListing(listing.id)}
                    onFocus={() => prefetchListing(listing.id)}
                    onTouchStart={() => prefetchListing(listing.id)}
                    className="block bg-white rounded-xl border border-slate-200 hover:border-teal-300 hover:shadow-sm transition-all overflow-hidden"
                  >
                    <div className="flex items-center gap-4 p-4">
                      {thumbUrl ? (
                        <div className="w-20 h-16 rounded-lg overflow-hidden bg-slate-100 flex-shrink-0">
                          <img src={thumbUrl} alt="" className="w-full h-full object-cover" />
                        </div>
                      ) : (
                        <div className="w-20 h-16 rounded-lg bg-slate-100 flex-shrink-0 flex items-center justify-center text-slate-300 text-xs">
                          sem foto
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        <h3 className="text-sm font-semibold text-slate-900 truncate">{title}</h3>
                        <div className="flex items-center gap-3 mt-1 text-xs text-slate-500">
                          <span className="font-medium text-teal-700">{formatEUR(listing.listing_price)}</span>
                          <span>·</span>
                          <span>{listing.listing_type ?? "—"}</span>
                          <span>·</span>
                          <span>{photoCount} {photoCount === 1 ? "foto" : "fotos"}</span>
                        </div>
                      </div>
                      <span
                        className="text-xs font-medium px-2.5 py-1 rounded-full flex-shrink-0"
                        style={{ backgroundColor: `${statusColor}15`, color: statusColor }}
                      >
                        {status}
                      </span>
                      <svg className="w-4 h-4 text-slate-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </div>
                  </Link>
                );
              })}
            </div>
          )}

          <div className="bg-slate-50 rounded-xl border border-dashed border-slate-200 px-5 py-4">
            <p className="text-sm text-slate-500">
              As publicações são criadas automaticamente a partir de deals no <Link href="/pipeline" className="text-teal-700 font-medium hover:underline">M4 — Pipeline</Link>.
              Propriedades devem ser registadas em <Link href="/properties" className="text-teal-700 font-medium hover:underline">M1 — Propriedades</Link>.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
