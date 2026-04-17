/**
 * listing_main — 1200×900 (ratio 4:3)
 *
 * Formato exigido por 90% dos portais imobiliários PT/BR (Idealista, Imovirtual,
 * SUPERCASA, CASA SAPO, OLX, Custojusto). Serve como foto principal da listagem.
 *
 * Layout: foto à esquerda (coluna maior), painel lateral direito com preço,
 * tipologia, área e meta. Discreto, legível a miniatura.
 */
import type { BrandKit, ListingData } from "../types";
import { formatPrice } from "../types";

interface Props {
  brand: BrandKit;
  listing: ListingData;
}

export function ListingMain({ brand, listing }: Props) {
  const primary = brand.primary_color ?? "#1a3e5c";
  const accent = brand.accent_color ?? "#c9a872";
  const logo = brand.logo_white_url ?? brand.logo_primary_url;

  return (
    <div
      style={{
        display: "flex",
        width: "100%",
        height: "100%",
        fontFamily: "Inter, sans-serif",
        color: "#ffffff",
        backgroundColor: primary,
      }}
    >
      {/* Coluna esquerda: foto 800x900 */}
      <div
        style={{
          display: "flex",
          position: "relative",
          width: 800,
          height: 900,
        }}
      >
        <img
          src={listing.primary_image_url}
          width="800"
          height="900"
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            objectFit: "cover",
          }}
        />
        {/* Badge tipologia */}
        {listing.typology && (
          <div
            style={{
              position: "absolute",
              top: 36,
              left: 36,
              display: "flex",
              padding: "10px 22px",
              borderRadius: 8,
              backgroundColor: accent,
              color: primary,
              fontSize: 28,
              fontWeight: 700,
              letterSpacing: "-0.3px",
            }}
          >
            {listing.typology}
          </div>
        )}
        {/* Energy rating */}
        {listing.energy_rating && (
          <div
            style={{
              position: "absolute",
              bottom: 36,
              left: 36,
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "8px 16px",
              borderRadius: 6,
              backgroundColor: "rgba(0,0,0,0.55)",
              fontSize: 18,
              fontWeight: 500,
              color: "#ffffff",
            }}
          >
            <span>Energia</span>
            <span
              style={{
                display: "flex",
                padding: "2px 10px",
                backgroundColor: "#2fba5f",
                borderRadius: 4,
                fontWeight: 700,
              }}
            >
              {listing.energy_rating}
            </span>
          </div>
        )}
      </div>

      {/* Coluna direita: painel 400x900 */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          width: 400,
          height: 900,
          padding: "48px 40px",
          justifyContent: "space-between",
          backgroundColor: primary,
        }}
      >
        {/* Top: logo */}
        <div style={{ display: "flex", height: 56 }}>
          {logo && <img src={logo} height="56" style={{ objectFit: "contain" }} />}
        </div>

        {/* Middle: conteudo */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 14,
          }}
        >
          {listing.location && (
            <div
              style={{
                display: "flex",
                fontSize: 20,
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
              fontSize: 36,
              fontWeight: 700,
              lineHeight: 1.12,
              color: "#ffffff",
              letterSpacing: "-0.8px",
            }}
          >
            {truncate(listing.title, 70)}
          </div>

          {/* Separador fino */}
          <div
            style={{
              display: "flex",
              height: 2,
              width: 60,
              backgroundColor: accent,
              marginTop: 8,
              marginBottom: 8,
            }}
          />

          {/* Preço */}
          {listing.price_eur != null && (
            <div
              style={{
                display: "flex",
                fontSize: 44,
                fontWeight: 700,
                color: accent,
                letterSpacing: "-1px",
              }}
            >
              {formatPrice(listing.price_eur)}
            </div>
          )}

          {/* Meta grid */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 10,
              marginTop: 12,
            }}
          >
            {listing.area_m2 != null && (
              <MetaRow label="Área bruta" value={`${listing.area_m2} m²`} />
            )}
            {listing.bedrooms != null && (
              <MetaRow label="Quartos" value={String(listing.bedrooms)} />
            )}
            {listing.bathrooms != null && (
              <MetaRow label="WCs" value={String(listing.bathrooms)} />
            )}
          </div>
        </div>

        {/* Footer: brand + website */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 4,
            fontSize: 16,
            color: "rgba(255,255,255,0.7)",
          }}
        >
          <span style={{ fontWeight: 600, color: "#ffffff" }}>{brand.brand_name}</span>
          {brand.website && <span>{stripProtocol(brand.website)}</span>}
        </div>
      </div>
    </div>
  );
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        paddingBottom: 6,
        borderBottom: "1px solid rgba(255,255,255,0.15)",
        fontSize: 18,
      }}
    >
      <span style={{ color: "rgba(255,255,255,0.65)" }}>{label}</span>
      <span style={{ color: "#ffffff", fontWeight: 600 }}>{value}</span>
    </div>
  );
}

function truncate(s: string, n: number): string {
  if (!s) return "";
  return s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s;
}

function stripProtocol(u: string): string {
  return u.replace(/^https?:\/\//, "").replace(/\/$/, "");
}
