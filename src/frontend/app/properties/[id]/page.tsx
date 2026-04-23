"use client";

import { useState } from "react";
import useSWR, { mutate as globalMutate } from "swr";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiDelete, apiPost, apiUpload, API_BASE } from "@/lib/api";
import { formatEUR } from "@/lib/utils";

interface PropertyPhoto {
  document_id?: string;
  url: string;
  filename?: string;
  order?: number;
  is_cover?: boolean;
}

interface Property {
  id: string;
  source?: string;
  district?: string;
  municipality?: string;
  parish?: string;
  address?: string;
  postal_code?: string;
  property_type?: string;
  typology?: string;
  gross_area_m2?: number;
  bedrooms?: number;
  bathrooms?: number;
  floor?: number;
  has_elevator?: boolean;
  has_parking?: boolean;
  construction_year?: number;
  energy_certificate?: string;
  condition?: string;
  asking_price?: number;
  status?: string;
  is_off_market?: boolean;
  contact_name?: string;
  contact_phone?: string;
  contact_email?: string;
  notes?: string;
  photos?: PropertyPhoto[];
  cover_photo_url?: string;
}

const CONDITION_LABELS: Record<string, string> = {
  novo: "Novo",
  renovado: "Renovado",
  usado: "Usado",
  para_renovar: "Para renovar",
  ruina: "Ruína",
};

export default function PropertyDetailPage() {
  const params = useParams();
  const propertyId = params?.id as string | undefined;
  const propertyKey = propertyId ? `/api/v1/properties/${propertyId}` : null;

  const { data: property, isLoading } = useSWR<Property | null>(propertyKey);
  const [uploading, setUploading] = useState(false);

  const photos: PropertyPhoto[] = Array.isArray(property?.photos)
    ? property!.photos!
    : [];

  async function reload() {
    if (propertyKey) await globalMutate(propertyKey);
  }

  async function uploadPhotos(files: FileList | File[]) {
    if (!propertyId) return;
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
      const res = await apiUpload(`/api/v1/properties/${propertyId}/photos`, fd);
      if (!res) {
        alert("Upload falhou");
        return;
      }
      await reload();
    } finally {
      setUploading(false);
    }
  }

  async function setCover(documentId: string) {
    if (!propertyId) return;
    const res = await apiPost(
      `/api/v1/properties/${propertyId}/photos/set-cover?document_id=${documentId}`
    );
    if (res) await reload();
  }

  async function deletePhoto(documentId: string) {
    if (!propertyId) return;
    if (!confirm("Remover esta foto?")) return;
    setUploading(true);
    try {
      await apiDelete(`/api/v1/properties/${propertyId}/photos/${documentId}`);
      await reload();
    } finally {
      setUploading(false);
    }
  }

  if (isLoading || !property) {
    return (
      <div className="space-y-6">
        <Link href="/properties" className="text-sm text-teal-700 hover:underline">
          ← Voltar a propriedades
        </Link>
        <div className="text-center py-16 text-slate-400">A carregar...</div>
      </div>
    );
  }

  const locParts = [property.parish, property.municipality, property.district]
    .filter(Boolean)
    .join(", ");

  return (
    <div className="space-y-6">
      <Link href="/properties" className="text-sm text-teal-700 hover:underline">
        ← Voltar a propriedades
      </Link>

      {/* Cabeçalho */}
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">
              {property.typology ? `${property.typology} em ` : ""}
              {property.municipality ?? "Propriedade"}
            </h1>
            {locParts && <p className="text-sm text-slate-500 mt-1">{locParts}</p>}
            {property.address && (
              <p className="text-sm text-slate-600 mt-1">{property.address}</p>
            )}
          </div>
          {property.asking_price ? (
            <span className="text-xl font-semibold text-teal-700">
              {formatEUR(property.asking_price)}
            </span>
          ) : null}
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-3 mt-6 text-sm">
          {property.gross_area_m2 != null && (
            <InfoRow label="Área" value={`${property.gross_area_m2} m²`} />
          )}
          {property.bedrooms != null && (
            <InfoRow label="Quartos" value={String(property.bedrooms)} />
          )}
          {property.bathrooms != null && (
            <InfoRow label="Casas de banho" value={String(property.bathrooms)} />
          )}
          {property.floor != null && (
            <InfoRow label="Andar" value={String(property.floor)} />
          )}
          {property.construction_year && (
            <InfoRow
              label="Ano construção"
              value={String(property.construction_year)}
            />
          )}
          {property.energy_certificate && (
            <InfoRow
              label="Certificado energético"
              value={property.energy_certificate}
            />
          )}
          {property.condition && (
            <InfoRow
              label="Estado"
              value={CONDITION_LABELS[property.condition] ?? property.condition}
            />
          )}
          {property.has_elevator ? <InfoRow label="Elevador" value="Sim" /> : null}
          {property.has_parking ? (
            <InfoRow label="Estacionamento" value="Sim" />
          ) : null}
          {property.is_off_market ? (
            <InfoRow label="Visibilidade" value="Off-market" />
          ) : null}
        </div>

        {(property.contact_name || property.contact_phone || property.contact_email) && (
          <div className="mt-6 pt-4 border-t border-slate-100">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
              Contacto do proprietário
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-x-6 gap-y-2 text-sm text-slate-700">
              {property.contact_name && <span>{property.contact_name}</span>}
              {property.contact_phone && <span>{property.contact_phone}</span>}
              {property.contact_email && <span>{property.contact_email}</span>}
            </div>
          </div>
        )}

        {property.notes && (
          <div className="mt-6 pt-4 border-t border-slate-100">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
              Notas
            </p>
            <p className="text-sm text-slate-700 whitespace-pre-wrap">{property.notes}</p>
          </div>
        )}
      </div>

      {/* Fotos */}
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Fotos</h2>
            <p className="text-xs text-slate-500 mt-1">
              Serão herdadas automaticamente pelo listing quando o deal avançar em M4.
            </p>
          </div>
          {photos.length > 0 && (
            <label
              className={`text-sm font-medium px-3 py-1.5 rounded-lg cursor-pointer ${
                uploading
                  ? "bg-slate-100 text-slate-400"
                  : "bg-teal-700 text-white hover:bg-teal-800"
              }`}
            >
              {uploading ? "A enviar..." : "+ Adicionar"}
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
          )}
        </div>

        {photos.length === 0 ? (
          <label
            className={`block border-2 border-dashed rounded-xl py-10 text-center cursor-pointer transition-colors ${
              uploading
                ? "border-slate-200 bg-slate-50"
                : "border-slate-300 hover:border-teal-500 hover:bg-teal-50/40"
            }`}
          >
            <svg
              className="w-8 h-8 mx-auto text-slate-400"
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
              const photoUrl = photo.url.startsWith("/")
                ? `${API_BASE}${photo.url}`
                : photo.url;
              const isCover =
                photo.is_cover ||
                (!!property.cover_photo_url &&
                  !!photo.document_id &&
                  property.cover_photo_url.includes(photo.document_id));
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
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-slate-800 font-medium">{value}</p>
    </div>
  );
}
