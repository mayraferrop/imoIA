/**
 * imoia-creatives — Cloudflare Worker que renderiza criativos M7 como PNG.
 *
 * Fluxo:
 *   Python backend (Render) → POST /render (X-Worker-Secret) → Satori + Resvg → PNG bytes
 *
 * Auth: header `X-Worker-Secret` obrigatório em /render. Secret configurado via
 *       `wrangler secret put CREATIVES_SECRET`.
 */
import { Hono } from "hono";
import { ImageResponse } from "workers-og";
import { TEMPLATE_SPECS, type RenderPayload } from "./types";
import { PropertyCard } from "./templates/property_card";
import { ListingMain } from "./templates/listing_main";

type Bindings = {
  CREATIVES_SECRET: string;
};

const app = new Hono<{ Bindings: Bindings }>();

app.get("/", (c) =>
  c.json({
    service: "imoia-creatives",
    version: "0.1.0",
    templates: Object.keys(TEMPLATE_SPECS),
  }),
);

app.post("/render", async (c) => {
  const expected = c.env.CREATIVES_SECRET;
  const got = c.req.header("x-worker-secret");
  if (!expected || got !== expected) {
    return c.json({ error: "unauthorized" }, 401);
  }

  let payload: RenderPayload;
  try {
    payload = await c.req.json();
  } catch {
    return c.json({ error: "invalid json" }, 400);
  }

  const spec = TEMPLATE_SPECS[payload.template];
  if (!spec) {
    return c.json({ error: `unknown template: ${payload.template}` }, 400);
  }

  const width = payload.width ?? spec.width;
  const height = payload.height ?? spec.height;

  let element;
  switch (payload.template) {
    case "property_card":
      element = PropertyCard({ brand: payload.brand, listing: payload.listing });
      break;
    case "listing_main":
      element = ListingMain({ brand: payload.brand, listing: payload.listing });
      break;
    // fb_post, ig_post, ig_story, linkedin_*: a seguir (Fase A incremental)
    default:
      return c.json(
        { error: `template not implemented yet: ${payload.template}` },
        501,
      );
  }

  try {
    const response = new ImageResponse(element as any, {
      width,
      height,
    });
    const bytes = await response.arrayBuffer();
    return new Response(bytes, {
      status: 200,
      headers: {
        "Content-Type": "image/png",
        "Cache-Control": "no-store",
        "X-Template": payload.template,
        "X-Dimensions": `${width}x${height}`,
      },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return c.json({ error: "render failed", detail: message }, 500);
  }
});

export default app;
