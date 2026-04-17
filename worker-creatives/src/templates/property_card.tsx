/**
 * property_card — 1080×1350 (ratio 4:5)
 *
 * Formato "hero" para IG feed / carousel / pitch deck.
 * Layout: foto full bleed com overlay gradient em baixo, título, preço destacado,
 * meta (tipologia, área, quartos) e logo da marca num canto.
 */
import type { BrandKit, ListingData } from "../types";
import { formatPrice } from "../types";

interface Props {
  brand: BrandKit;
  listing: ListingData;
}

export function PropertyCard({ brand, listing }: Props) {
  const primary = brand.primary_color ?? "#1a3e5c";
  const accent = brand.accent_color ?? "#c9a872";
  const logo = brand.logo_white_url ?? brand.logo_primary_url;

  const meta: string[] = [];
  if (listing.typology) meta.push(listing.typology);
  if (listing.area_m2) meta.push(`${listing.area_m2} m²`);
  if (listing.bedrooms) meta.push(`${listing.bedrooms} quartos`);

  return (
    <div
      style={{
        display: "flex",
        width: "100%",
        height: "100%",
        position: "relative",
        fontFamily: "Inter, sans-serif",
        color: "#ffffff",
        backgroundColor: primary,
      }}
    >
      {/* Foto de fundo */}
      <img
        src={listing.primary_image_url}
        width="1080"
        height="1350"
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          objectFit: "cover",
        }}
      />

      {/* Gradient overlay no fundo para legibilidade */}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          height: "62%",
          display: "flex",
          background:
            "linear-gradient(180deg, rgba(15,25,45,0) 0%, rgba(15,25,45,0.55) 45%, rgba(15,25,45,0.95) 100%)",
        }}
      />

      {/* Logo no topo direito */}
      {logo && (
        <div
          style={{
            position: "absolute",
            top: 48,
            right: 48,
            display: "flex",
          }}
        >
          <img src={logo} height="56" style={{ objectFit: "contain" }} />
        </div>
      )}

      {/* Badge preço no topo esquerdo */}
      {listing.price_eur != null && (
        <div
          style={{
            position: "absolute",
            top: 48,
            left: 48,
            display: "flex",
            alignItems: "center",
            padding: "14px 24px",
            backgroundColor: accent,
            borderRadius: 999,
            fontSize: 34,
            fontWeight: 700,
            color: primary,
            letterSpacing: "-0.5px",
          }}
        >
          {formatPrice(listing.price_eur)}
        </div>
      )}

      {/* Bloco inferior: localização + título + meta */}
      <div
        style={{
          position: "absolute",
          left: 56,
          right: 56,
          bottom: 64,
          display: "flex",
          flexDirection: "column",
          gap: 18,
        }}
      >
        {listing.location && (
          <div
            style={{
              display: "flex",
              fontSize: 26,
              fontWeight: 500,
              letterSpacing: "2px",
              textTransform: "uppercase",
              color: accent,
            }}
          >
            {listing.location}
          </div>
        )}

        <div
          style={{
            display: "flex",
            fontSize: 68,
            fontWeight: 700,
            lineHeight: 1.05,
            color: "#ffffff",
            letterSpacing: "-1.5px",
          }}
        >
          {truncate(listing.title, 80)}
        </div>

        {meta.length > 0 && (
          <div
            style={{
              display: "flex",
              gap: 16,
              marginTop: 8,
            }}
          >
            {meta.map((m, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  padding: "10px 20px",
                  borderRadius: 8,
                  backgroundColor: "rgba(255,255,255,0.14)",
                  border: "1px solid rgba(255,255,255,0.22)",
                  fontSize: 26,
                  fontWeight: 500,
                  color: "#ffffff",
                }}
              >
                {m}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function truncate(s: string, n: number): string {
  if (!s) return "";
  return s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s;
}
