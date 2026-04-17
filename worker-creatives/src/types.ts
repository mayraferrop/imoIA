/**
 * Tipos partilhados entre templates e o handler principal.
 * O payload reflete o que o backend Python envia em creative_service.py.
 */

export type CreativeType =
  | "property_card"       // 1080x1350  — IG feed 4:5 / carousel
  | "listing_main"        // 1200x900   — Idealista/Imovirtual/SAPO/OLX
  | "fb_post"             // 1200x630   — Facebook feed
  | "fb_carousel_card"    // 1080x1080  — FB carousel
  | "ig_post"             // 1080x1080  — IG feed 1:1
  | "ig_story"            // 1080x1920  — IG/FB story
  | "linkedin_post"       // 1200x627   — LinkedIn feed
  | "linkedin_square";    // 1200x1200  — LinkedIn square

export interface BrandKit {
  brand_name: string;
  tagline?: string | null;
  logo_primary_url?: string | null;
  logo_white_url?: string | null;
  logo_icon_url?: string | null;
  primary_color?: string | null;
  secondary_color?: string | null;
  accent_color?: string | null;
  font_heading?: string | null;
  font_body?: string | null;
  website?: string | null;
  phone?: string | null;
  email?: string | null;
}

export interface ListingData {
  title: string;
  short_description?: string | null;
  price_eur?: number | null;
  location?: string | null;          // ex: "Campanhã, Porto"
  typology?: string | null;          // ex: "T2"
  area_m2?: number | null;
  bedrooms?: number | null;
  bathrooms?: number | null;
  energy_rating?: string | null;     // ex: "A+", "B"
  highlights?: string[];
  primary_image_url: string;         // URL assinado ou público acessível
}

export interface RenderPayload {
  template: CreativeType;
  brand: BrandKit;
  listing: ListingData;
  // Override opcional: útil para debug/teste de resoluções custom.
  width?: number;
  height?: number;
}

export interface TemplateSpec {
  width: number;
  height: number;
}

export const TEMPLATE_SPECS: Record<CreativeType, TemplateSpec> = {
  property_card:      { width: 1080, height: 1350 },
  listing_main:       { width: 1200, height: 900 },
  fb_post:            { width: 1200, height: 630 },
  fb_carousel_card:   { width: 1080, height: 1080 },
  ig_post:            { width: 1080, height: 1080 },
  ig_story:           { width: 1080, height: 1920 },
  linkedin_post:      { width: 1200, height: 627 },
  linkedin_square:    { width: 1200, height: 1200 },
};

export function formatPrice(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "";
  return new Intl.NumberFormat("pt-PT", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value);
}
