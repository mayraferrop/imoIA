"use client";

import { useState, useEffect, useCallback, useTransition, memo } from "react";
import useSWR, { mutate as globalMutate } from "swr";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  fetcher,
  apiPost,
  apiPostStrict,
  apiPatch,
  apiUpload,
  apiDelete,
  API_BASE,
} from "@/lib/api";
import { formatEUR, cn } from "@/lib/utils";

interface ListingPhoto {
  document_id?: string;
  url: string;
  filename?: string;
  order?: number;
  is_cover?: boolean;
}

interface Listing {
  id: string;
  title_pt?: string;
  title_en?: string;
  title_pt_br?: string;
  title_fr?: string;
  title_zh?: string;
  description_pt?: string;
  description_en?: string;
  description_pt_br?: string;
  description_fr?: string;
  description_zh?: string;
  short_description_pt?: string;
  listing_type?: string;
  listing_price?: number;
  status?: string;
  slug?: string;
  highlights?: string[];
  content_whatsapp?: string;
  content_instagram_post?: string;
  content_facebook_post?: string;
  content_linkedin?: string;
  content_portal?: string;
  content_email_subject?: string;
  content_email_body?: string;
  meta_title?: string;
  meta_description?: string;
  notes?: string;
  photos?: ListingPhoto[];
  cover_photo_url?: string;
  deal_id?: string;
}

interface Creative {
  id: string;
  creative_type?: string;
  format?: string;
  width?: number;
  height?: number;
  document_id?: string;
  file_url?: string;
  signed_url?: string | null;
}

interface BrandKit {
  brand_name?: string;
  tagline?: string;
  color_primary?: string;
  color_secondary?: string;
  color_accent?: string;
  contact_phone?: string;
  website_url?: string;
  logo_primary_url?: string;
}

interface PropertyInfo {
  typology?: string;
  gross_area_m2?: number;
  bedrooms?: number;
  bathrooms?: number;
  municipality?: string;
  parish?: string;
  energy_certificate?: string;
  property_type?: string;
}

interface DealInfo {
  id: string;
  property_id?: string;
  title?: string;
}

const CREATIVE_LABELS: Record<string, string> = {
  ig_post: "Instagram Post",
  ig_story: "Instagram Story",
  fb_post: "Facebook Post",
  property_card: "Property Card",
  whatsapp_card: "WhatsApp Card",
  flyer: "Flyer A4",
  listing_main: "Portal (capa)",
};

const STATUS_COLORS: Record<string, string> = {
  draft: "#94A3B8",
  active: "#16A34A",
  paused: "#D97706",
  sold: "#7C3AED",
  archived: "#64748B",
};

type Tab = "conteudo" | "fotos" | "criativos" | "emails" | "preview";

interface EmailCampaign {
  id: string;
  campaign_type?: string;
  subject?: string;
  status?: string;
  language?: string;
  recipient_count?: number;
  sent_at?: string | null;
  delivered?: number;
  opened?: number;
  clicked?: number;
  open_rate?: number;
  click_rate?: number;
  created_at?: string | null;
}

export default function ListingDetailPage() {
  const params = useParams<{ listing_id: string }>();
  const router = useRouter();
  const listingId = params?.listing_id;

  const listingKey = listingId ? `/api/v1/marketing/listings/${listingId}` : null;
  const creativesKey = listingId
    ? `/api/v1/marketing/listings/${listingId}/creatives`
    : null;
  const emailsKey = listingId
    ? `/api/v1/marketing/listings/${listingId}/emails`
    : null;
  const brandKitKey = "/api/v1/marketing/brand-kit";

  const { data: listing } = useSWR<Listing | null>(listingKey);
  const { data: creativesData } = useSWR<Creative[] | null>(creativesKey);
  const { data: emailsData } = useSWR<EmailCampaign[] | null>(emailsKey);
  const { data: brandKit } = useSWR<BrandKit | null>(brandKitKey);
  const creatives = creativesData ?? [];
  const emails = emailsData ?? [];

  const dealKey = listing?.deal_id ? `/api/v1/deals/${listing.deal_id}` : null;
  const { data: deal } = useSWR<DealInfo | null>(dealKey);

  const propertyKey = deal?.property_id
    ? `/api/v1/properties/${deal.property_id}`
    : null;
  const { data: property } = useSWR<PropertyInfo | null>(propertyKey);

  const loading = listing === undefined;

  const [tab, setTabRaw] = useState<Tab>("fotos");
  const [, startTabTransition] = useTransition();
  const setTab = useCallback((t: Tab) => {
    startTabTransition(() => setTabRaw(t));
  }, []);
  const [uploading, setUploading] = useState(false);
  const [regenerating, setRegenerating] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!listingId) return;
    await Promise.all([
      globalMutate(listingKey),
      globalMutate(creativesKey),
      globalMutate(emailsKey),
      globalMutate(brandKitKey),
    ]);
  }, [listingId, listingKey, creativesKey, emailsKey]);

  const [emailBusy, setEmailBusy] = useState(false);
  const [emailError, setEmailError] = useState<string | null>(null);
  const [approveBusy, setApproveBusy] = useState(false);
  const [approveError, setApproveError] = useState<string | null>(null);

  async function approveListing() {
    if (!listingId) return;
    setApproveBusy(true);
    setApproveError(null);
    try {
      const r = await apiPostStrict(
        `/api/v1/marketing/listings/${listingId}/approve`
      );
      if (!r.ok) {
        setApproveError(`HTTP ${r.status}: ${r.error ?? "(sem detalhe)"}`);
        return;
      }
      await globalMutate(listingKey);
    } finally {
      setApproveBusy(false);
    }
  }

  async function generateEmail(campaignType: string) {
    if (!listingId) return;
    setEmailBusy(true);
    setEmailError(null);
    try {
      const r = await apiPostStrict(
        `/api/v1/marketing/listings/${listingId}/email?campaign_type=${campaignType}&language=pt-PT`
      );
      if (!r.ok) {
        setEmailError(`HTTP ${r.status}: ${r.error ?? "(sem detalhe)"}`);
        return;
      }
      await globalMutate(emailsKey);
    } finally {
      setEmailBusy(false);
    }
  }

  async function sendCampaign(campaignId: string) {
    const raw = prompt(
      "Emails destinatários (separados por vírgula):",
      "mayaraferrop@gmail.com"
    );
    if (!raw) return;
    const recipients = raw
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    if (recipients.length === 0) return;
    setEmailBusy(true);
    setEmailError(null);
    try {
      const r = await apiPostStrict(
        `/api/v1/marketing/email/${campaignId}/send`,
        recipients
      );
      if (!r.ok) {
        setEmailError(`HTTP ${r.status}: ${r.error ?? "(sem detalhe)"}`);
        return;
      }
      await globalMutate(emailsKey);
    } finally {
      setEmailBusy(false);
    }
  }

  async function uploadPhotos(files: FileList | File[]) {
    if (!listingId) return;
    const arr = Array.from(files);
    if (arr.length === 0) return;
    const tooBig = arr.find((f) => f.size > 15 * 1024 * 1024);
    if (tooBig) {
      alert(`Ficheiro excede 15MB: ${tooBig.name}`);
      return;
    }
    setUploading(true);
    try {
      const fd = new FormData();
      for (const f of arr) fd.append("files", f);
      const res = await apiUpload(`/api/v1/marketing/listings/${listingId}/photos`, fd);
      if (!res) {
        alert("Upload falhou");
        return;
      }
      await load();
    } finally {
      setUploading(false);
    }
  }

  async function setCover(documentId: string) {
    if (!listingId) return;
    const res = await apiPost(
      `/api/v1/marketing/listings/${listingId}/photos/set-cover?document_id=${documentId}`
    );
    if (res) await load();
  }

  async function deletePhoto(documentId: string) {
    if (!listingId) return;
    if (!confirm("Remover esta foto?")) return;
    setUploading(true);
    try {
      await apiDelete(`/api/v1/marketing/listings/${listingId}/photos/${documentId}`);
      await load();
    } finally {
      setUploading(false);
    }
  }

  async function generateCreatives() {
    if (!listingId) return;
    await apiPost(`/api/v1/marketing/listings/${listingId}/creatives/generate-all`);
    await load();
  }

  async function regenerateField(field: string, language?: string, channel?: string) {
    if (!listingId) return;
    const key = `${field}:${language ?? ""}:${channel ?? ""}`;
    setRegenerating(key);
    try {
      await apiPost(`/api/v1/marketing/listings/${listingId}/regenerate`, {
        field, language, channel,
      });
      await load();
    } finally {
      setRegenerating(null);
    }
  }

  async function saveField(field: keyof Listing, value: string) {
    if (!listingId) return;
    await apiPatch(`/api/v1/marketing/listings/${listingId}`, { [field]: value });
    await load();
  }

  if (loading) {
    return (
      <div className="p-8 text-center text-slate-400">A carregar publicação...</div>
    );
  }

  if (!listing) {
    return (
      <div className="p-8 text-center">
        <p className="text-slate-500">Publicação não encontrada</p>
        <Link href="/marketing" className="text-teal-700 text-sm mt-2 inline-block">
          Voltar a Marketing
        </Link>
      </div>
    );
  }

  const title = listing.title_pt || listing.notes || "Publicação";
  const status = listing.status ?? "draft";
  const statusColor = STATUS_COLORS[status] ?? "#94A3B8";
  const photos = listing.photos ?? [];
  const cover = photos.find(
    (p) =>
      p.is_cover ||
      (!!p.document_id &&
        !!listing.cover_photo_url &&
        listing.cover_photo_url.includes(p.document_id))
  );
  const coverUrl = cover?.url ?? listing.cover_photo_url;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 border-b border-slate-200 pb-4">
        <div className="flex-1">
          <button
            onClick={() => router.push("/marketing")}
            className="text-xs text-slate-500 hover:text-slate-700 mb-2"
          >
            ← Marketing
          </button>
          <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
          <div className="flex items-center gap-3 mt-2 text-sm text-slate-500">
            <span className="font-semibold text-teal-700">
              {formatEUR(listing.listing_price)}
            </span>
            <span>·</span>
            <span>{listing.listing_type ?? "—"}</span>
            <span>·</span>
            <span
              className="text-xs font-medium px-2 py-0.5 rounded-full"
              style={{ backgroundColor: `${statusColor}15`, color: statusColor }}
            >
              {status}
            </span>
            {listing.slug && (
              <>
                <span>·</span>
                <code className="text-xs bg-slate-100 px-1.5 py-0.5 rounded">
                  {listing.slug}
                </code>
              </>
            )}
          </div>
          {approveError && (
            <div className="mt-2 rounded-md border border-red-200 bg-red-50 px-3 py-1.5 text-sm text-red-700">
              {approveError}
            </div>
          )}
        </div>
        {status === "draft" && (
          <button
            onClick={approveListing}
            disabled={approveBusy}
            className="rounded-md bg-teal-700 px-4 py-2 text-sm font-medium text-white hover:bg-teal-800 disabled:opacity-50"
          >
            {approveBusy ? "Aprovando…" : "Aprovar"}
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-slate-200">
        {[
          { key: "fotos" as const, label: `Fotos (${photos.length})` },
          { key: "criativos" as const, label: `Criativos (${creatives.length})` },
          { key: "conteudo" as const, label: "Conteúdo" },
          { key: "emails" as const, label: `Emails (${emails.length})` },
          { key: "preview" as const, label: "Preview" },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={cn(
              "px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors",
              tab === t.key
                ? "border-teal-700 text-teal-700"
                : "border-transparent text-slate-500 hover:text-slate-700"
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* TAB FOTOS */}
      {tab === "fotos" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-500">
              Estas fotos alimentam criativos, portais e publicação no site.
              Use JPG/PNG/WebP em resolução alta (≥ 1920×1080 recomendado).
            </p>
            <label
              className={cn(
                "text-sm font-medium px-3 py-1.5 rounded-lg cursor-pointer transition-colors",
                uploading
                  ? "bg-slate-100 text-slate-400 cursor-wait"
                  : "bg-teal-700 text-white hover:bg-teal-800"
              )}
            >
              {uploading ? "A enviar..." : "+ Adicionar fotos"}
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                multiple
                className="hidden"
                disabled={uploading}
                onChange={(e) => {
                  if (e.target.files && e.target.files.length > 0) {
                    uploadPhotos(e.target.files);
                    e.target.value = "";
                  }
                }}
              />
            </label>
          </div>

          {photos.length === 0 ? (
            <label
              className={cn(
                "block border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors",
                uploading
                  ? "border-slate-200 bg-slate-50 cursor-wait"
                  : "border-slate-300 hover:border-teal-500 hover:bg-teal-50/30"
              )}
            >
              <svg
                className="mx-auto w-10 h-10 text-slate-300"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                />
              </svg>
              <p className="text-sm text-slate-600 mt-3">
                {uploading ? "A enviar..." : "Arraste ou clique para adicionar fotos"}
              </p>
              <p className="text-xs text-slate-400 mt-1">
                JPG, PNG ou WebP — máx 15MB por ficheiro
              </p>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                multiple
                className="hidden"
                disabled={uploading}
                onChange={(e) => {
                  if (e.target.files && e.target.files.length > 0) {
                    uploadPhotos(e.target.files);
                    e.target.value = "";
                  }
                }}
              />
            </label>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {photos.map((photo) => {
                const photoUrl = photo.url;
                const isCover =
                  photo.is_cover ||
                  (!!listing.cover_photo_url &&
                    !!photo.document_id &&
                    listing.cover_photo_url.includes(photo.document_id));
                return (
                  <div
                    key={photo.document_id ?? photo.url}
                    className="relative group aspect-[4/3] bg-slate-100 rounded-lg overflow-hidden border border-slate-200"
                  >
                    <img
                      src={photoUrl}
                      alt={photo.filename ?? "foto"}
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.opacity = "0.3";
                      }}
                    />
                    {isCover && (
                      <span className="absolute top-2 left-2 text-[11px] font-semibold bg-teal-600 text-white px-2 py-0.5 rounded">
                        CAPA
                      </span>
                    )}
                    <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-end justify-center gap-2 p-2">
                      {!isCover && photo.document_id && (
                        <button
                          onClick={() => setCover(photo.document_id!)}
                          className="text-xs font-medium bg-white/90 hover:bg-white text-slate-800 px-2 py-1 rounded"
                        >
                          Definir capa
                        </button>
                      )}
                      {photo.document_id && (
                        <button
                          onClick={() => deletePhoto(photo.document_id!)}
                          className="text-xs font-medium bg-red-500/90 hover:bg-red-500 text-white px-2 py-1 rounded"
                        >
                          Remover
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* TAB CRIATIVOS */}
      {tab === "criativos" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-500">
              Imagens geradas a partir das fotos e conteúdo. Regenere depois de
              editar cover ou textos.
            </p>
            <button
              onClick={generateCreatives}
              className="text-sm font-medium bg-teal-700 text-white px-3 py-1.5 rounded-lg hover:bg-teal-800"
            >
              {creatives.length ? "Regenerar todos" : "Gerar criativos"}
            </button>
          </div>

          {creatives.length === 0 ? (
            <div className="border border-dashed border-slate-200 rounded-xl p-12 text-center text-slate-400">
              Sem criativos gerados.
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {creatives.map((c) => {
                const label =
                  CREATIVE_LABELS[c.creative_type ?? ""] ?? c.creative_type;
                const downloadUrl = c.document_id
                  ? `${API_BASE}/api/v1/documents/${c.document_id}/download`
                  : null;
                const previewUrl = c.signed_url || downloadUrl;
                const isVertical = (c.height ?? 0) > (c.width ?? 0);
                return (
                  <div
                    key={c.id}
                    className="bg-white border border-slate-200 rounded-xl overflow-hidden"
                  >
                    {previewUrl && c.format === "png" ? (
                      <div
                        className={cn(
                          "bg-slate-100 overflow-hidden",
                          isVertical ? "aspect-[4/5]" : "aspect-[4/3]"
                        )}
                      >
                        <img
                          src={previewUrl}
                          alt={label}
                          className="w-full h-full object-cover"
                          onError={(e) => {
                            (e.target as HTMLImageElement).style.display = "none";
                          }}
                        />
                      </div>
                    ) : (
                      <div className="aspect-[4/3] bg-slate-100 flex items-center justify-center text-slate-300 text-3xl">
                        {c.format === "pdf" ? "PDF" : "IMG"}
                      </div>
                    )}
                    <div className="p-3">
                      <p className="text-sm font-medium text-slate-900">{label}</p>
                      <p className="text-xs text-slate-500">
                        {c.width}×{c.height} · {c.format?.toUpperCase()}
                      </p>
                      {(previewUrl || downloadUrl) && (
                        <a
                          href={previewUrl || downloadUrl || "#"}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs font-medium text-teal-700 hover:text-teal-800 mt-1.5 inline-block"
                        >
                          Download
                        </a>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* TAB CONTEÚDO */}
      {tab === "conteudo" && (
        <div className="space-y-6">
          <ContentField
            label="Título (PT)"
            value={listing.title_pt}
            onSave={(v) => saveField("title_pt", v)}
            onRegenerate={() => regenerateField("title", "pt-PT")}
            busy={regenerating?.startsWith("title:pt-PT")}
          />
          <ContentField
            label="Descrição curta (PT)"
            value={listing.short_description_pt}
            multiline
            onSave={(v) => saveField("short_description_pt", v)}
            onRegenerate={() => regenerateField("short_description", "pt-PT")}
            busy={regenerating?.startsWith("short_description:pt-PT")}
          />
          <ContentField
            label="Descrição completa (PT)"
            value={listing.description_pt}
            multiline
            rows={6}
            onSave={(v) => saveField("description_pt", v)}
            onRegenerate={() => regenerateField("description", "pt-PT")}
            busy={regenerating?.startsWith("description:pt-PT")}
          />

          <div className="pt-2 border-t border-slate-100">
            <h3 className="text-sm font-semibold text-slate-700 mb-3">
              Conteúdo por canal
            </h3>
            <div className="space-y-4">
              <ContentField
                label="WhatsApp"
                value={listing.content_whatsapp}
                multiline rows={4}
                onSave={(v) => saveField("content_whatsapp", v)}
                onRegenerate={() => regenerateField("content", undefined, "whatsapp")}
                busy={regenerating === "content::whatsapp"}
              />
              <ContentField
                label="Instagram"
                value={listing.content_instagram_post}
                multiline rows={4}
                onSave={(v) => saveField("content_instagram_post", v)}
                onRegenerate={() => regenerateField("content", undefined, "instagram_post")}
                busy={regenerating === "content::instagram_post"}
              />
              <ContentField
                label="Facebook"
                value={listing.content_facebook_post}
                multiline rows={4}
                onSave={(v) => saveField("content_facebook_post", v)}
                onRegenerate={() => regenerateField("content", undefined, "facebook_post")}
                busy={regenerating === "content::facebook_post"}
              />
              <ContentField
                label="Portal (Idealista/Imovirtual)"
                value={listing.content_portal}
                multiline rows={5}
                onSave={(v) => saveField("content_portal", v)}
                onRegenerate={() => regenerateField("content", undefined, "portal")}
                busy={regenerating === "content::portal"}
              />
            </div>
          </div>

          <div className="pt-2 border-t border-slate-100">
            <h3 className="text-sm font-semibold text-slate-700 mb-3">SEO</h3>
            <div className="space-y-4">
              <ContentField
                label="Meta title"
                value={listing.meta_title}
                onSave={(v) => saveField("meta_title", v)}
              />
              <ContentField
                label="Meta description"
                value={listing.meta_description}
                multiline rows={2}
                onSave={(v) => saveField("meta_description", v)}
              />
            </div>
          </div>
        </div>
      )}

      {/* TAB EMAILS */}
      {tab === "emails" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <p className="text-sm text-slate-500">
              Campanhas email geradas a partir desta publicação. Envio via Resend.
            </p>
            <div className="flex gap-2 flex-wrap">
              {["new_property", "price_reduction", "open_house", "follow_up"].map((ct) => (
                <button
                  key={ct}
                  disabled={emailBusy}
                  onClick={() => generateEmail(ct)}
                  className={cn(
                    "text-xs font-medium px-3 py-1.5 rounded-lg border",
                    emailBusy
                      ? "bg-slate-100 text-slate-400 border-slate-200 cursor-wait"
                      : "text-indigo-700 border-indigo-300 hover:bg-indigo-50"
                  )}
                >
                  + {ct}
                </button>
              ))}
            </div>
          </div>

          {emailError && (
            <div className="bg-rose-50 border border-rose-200 text-rose-700 text-sm rounded-lg px-4 py-3 whitespace-pre-wrap break-words">
              {emailError}
            </div>
          )}

          {emails.length === 0 ? (
            <div className="text-sm text-slate-400 italic p-6 border border-dashed border-slate-200 rounded-lg text-center">
              Ainda não há campanhas. Gera uma acima.
            </div>
          ) : (
            <div className="space-y-2">
              {emails.map((c) => {
                const st = c.status ?? "draft";
                const isDraft = st === "draft";
                return (
                  <div
                    key={c.id}
                    className="border border-slate-200 rounded-lg p-4 flex flex-col gap-2"
                  >
                    <div className="flex items-start justify-between gap-4 flex-wrap">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-slate-100 text-slate-700">
                            {c.campaign_type ?? "—"}
                          </span>
                          <span
                            className="text-[10px] font-semibold px-1.5 py-0.5 rounded"
                            style={{
                              backgroundColor:
                                st === "sent"
                                  ? "#16A34A15"
                                  : st === "failed"
                                  ? "#DC262615"
                                  : "#94A3B815",
                              color:
                                st === "sent"
                                  ? "#16A34A"
                                  : st === "failed"
                                  ? "#DC2626"
                                  : "#64748B",
                            }}
                          >
                            {st}
                          </span>
                          <span className="text-[10px] text-slate-400">
                            {c.language ?? "—"}
                          </span>
                        </div>
                        <p className="text-sm font-medium text-slate-800 mt-1 truncate">
                          {c.subject ?? "(sem assunto)"}
                        </p>
                        <p className="text-[11px] text-slate-500 mt-1">
                          {c.recipient_count ?? 0} destinatários ·{" "}
                          {c.delivered ?? 0} entregues ·{" "}
                          {c.opened ?? 0} abertos ·{" "}
                          {c.clicked ?? 0} cliques
                          {c.sent_at && (
                            <>
                              {" · enviado "}
                              {new Date(c.sent_at).toLocaleString("pt-PT")}
                            </>
                          )}
                        </p>
                      </div>
                      {isDraft && (
                        <button
                          disabled={emailBusy}
                          onClick={() => sendCampaign(c.id)}
                          className={cn(
                            "text-xs font-medium px-3 py-1.5 rounded-lg",
                            emailBusy
                              ? "bg-slate-100 text-slate-400 cursor-wait"
                              : "bg-teal-700 text-white hover:bg-teal-800"
                          )}
                        >
                          Enviar
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* TAB PREVIEW */}
      {tab === "preview" && (
        <ListingPreview
          listing={listing}
          property={property ?? null}
          brandKit={brandKit ?? null}
          coverUrl={coverUrl}
          photos={photos}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ContentField — editor inline com save e regenerar
// ---------------------------------------------------------------------------

const ContentField = memo(function ContentField({
  label,
  value,
  multiline,
  rows = 3,
  onSave,
  onRegenerate,
  busy,
}: {
  label: string;
  value?: string;
  multiline?: boolean;
  rows?: number;
  onSave: (v: string) => Promise<void> | void;
  onRegenerate?: () => Promise<void> | void;
  busy?: boolean | null;
}) {
  const [local, setLocal] = useState(value ?? "");
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    setLocal(value ?? "");
  }, [value]);
  const dirty = local !== (value ?? "");

  async function handleSave() {
    setSaving(true);
    try {
      await onSave(local);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label className="text-xs font-medium text-slate-600">{label}</label>
        <div className="flex items-center gap-2">
          {dirty && (
            <button
              onClick={handleSave}
              disabled={saving}
              className="text-xs font-medium text-teal-700 hover:text-teal-800 disabled:opacity-50"
            >
              {saving ? "A guardar..." : "Guardar"}
            </button>
          )}
          {onRegenerate && (
            <button
              onClick={onRegenerate}
              disabled={!!busy}
              className="text-xs font-medium text-slate-500 hover:text-slate-700 disabled:opacity-50"
            >
              {busy ? "A regenerar..." : "Regenerar IA"}
            </button>
          )}
        </div>
      </div>
      {multiline ? (
        <textarea
          value={local}
          onChange={(e) => setLocal(e.target.value)}
          rows={rows}
          className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
        />
      ) : (
        <input
          type="text"
          value={local}
          onChange={(e) => setLocal(e.target.value)}
          className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
        />
      )}
    </div>
  );
});

// ---------------------------------------------------------------------------
// ListingPreview — render estilo habta.eu
// ---------------------------------------------------------------------------

const ListingPreview = memo(function ListingPreview({
  listing,
  property,
  brandKit,
  coverUrl,
  photos,
}: {
  listing: Listing;
  property: PropertyInfo | null;
  brandKit: BrandKit | null;
  coverUrl?: string;
  photos: ListingPhoto[];
}) {
  const primary = brandKit?.color_primary ?? "#1E3A5F";
  const accent = brandKit?.color_accent ?? "#E76F51";
  const chips: string[] = [];
  if (property?.typology) chips.push(property.typology);
  if (property?.bedrooms) chips.push(`${property.bedrooms} quartos`);
  if (property?.bathrooms) chips.push(`${property.bathrooms} WC`);
  if (property?.gross_area_m2) chips.push(`${property.gross_area_m2} m²`);
  if (property?.energy_certificate) chips.push(`Energia ${property.energy_certificate}`);
  const location = [property?.parish, property?.municipality].filter(Boolean).join(", ");

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="px-4 py-2 bg-slate-50 border-b border-slate-100 text-xs text-slate-500 flex items-center justify-between">
        <span>Preview — aproximação da página pública (habta.eu e portais)</span>
        {listing.slug && (
          <code className="text-xs bg-white border border-slate-200 px-2 py-0.5 rounded">
            /{listing.slug}
          </code>
        )}
      </div>

      {/* Hero */}
      <div className="relative aspect-[16/9] bg-slate-200 overflow-hidden">
        {coverUrl ? (
          <img
            src={coverUrl}
            alt={listing.title_pt ?? ""}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-slate-400 text-sm">
            Sem foto de capa
          </div>
        )}
        <div
          className="absolute inset-x-0 bottom-0 p-6 text-white"
          style={{
            background:
              "linear-gradient(to top, rgba(0,0,0,0.75), rgba(0,0,0,0))",
          }}
        >
          <div className="flex items-end justify-between gap-4">
            <div>
              <h2 className="text-2xl md:text-3xl font-bold">
                {listing.title_pt ?? "Sem título"}
              </h2>
              {location && (
                <p className="text-sm mt-1 opacity-90">{location}</p>
              )}
            </div>
            <div
              className="text-xl md:text-2xl font-bold whitespace-nowrap"
              style={{ color: accent }}
            >
              {formatEUR(listing.listing_price)}
            </div>
          </div>
        </div>
      </div>

      {/* Body */}
      <div className="p-6 space-y-6">
        {chips.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {chips.map((chip) => (
              <span
                key={chip}
                className="text-xs font-medium px-3 py-1 rounded-full"
                style={{
                  backgroundColor: `${primary}10`,
                  color: primary,
                }}
              >
                {chip}
              </span>
            ))}
          </div>
        )}

        {listing.short_description_pt && (
          <p className="text-sm text-slate-700 leading-relaxed italic">
            {listing.short_description_pt}
          </p>
        )}

        {listing.description_pt && (
          <div>
            <h3
              className="text-sm font-semibold mb-2"
              style={{ color: primary }}
            >
              Descrição
            </h3>
            <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">
              {listing.description_pt}
            </p>
          </div>
        )}

        {listing.highlights && listing.highlights.length > 0 && (
          <div>
            <h3
              className="text-sm font-semibold mb-2"
              style={{ color: primary }}
            >
              Destaques
            </h3>
            <ul className="text-sm text-slate-700 space-y-1">
              {listing.highlights.map((h, i) => (
                <li key={i} className="flex gap-2">
                  <span style={{ color: accent }}>•</span>
                  <span>{h}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {photos.length > 1 && (
          <div>
            <h3
              className="text-sm font-semibold mb-2"
              style={{ color: primary }}
            >
              Galeria
            </h3>
            <div className="grid grid-cols-3 md:grid-cols-4 gap-2">
              {photos.slice(0, 12).map((photo) => {
                const src = photo.url;
                return (
                  <div
                    key={photo.document_id ?? photo.url}
                    className="aspect-square bg-slate-100 rounded overflow-hidden"
                  >
                    <img
                      src={src}
                      alt=""
                      className="w-full h-full object-cover"
                    />
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {brandKit && (
          <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
            <div className="flex items-center gap-3">
              {brandKit.logo_primary_url && (
                <img
                  src={brandKit.logo_primary_url}
                  alt={brandKit.brand_name}
                  className="h-8 object-contain"
                />
              )}
              <div>
                <p className="text-sm font-semibold" style={{ color: primary }}>
                  {brandKit.brand_name}
                </p>
                {brandKit.tagline && (
                  <p className="text-xs text-slate-500">{brandKit.tagline}</p>
                )}
              </div>
            </div>
            <div className="text-xs text-slate-500 text-right space-y-0.5">
              {brandKit.contact_phone && <p>{brandKit.contact_phone}</p>}
              {brandKit.website_url && <p>{brandKit.website_url}</p>}
            </div>
          </div>
        )}
      </div>
    </div>
  );
});
