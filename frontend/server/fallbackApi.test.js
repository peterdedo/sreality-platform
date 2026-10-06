import { describe, expect, it } from "vitest";
import { handleFallback, LISTINGS } from "./fallbackApi.js";
import { isRailwayMiss } from "./railwayProxy.js";

describe("handleFallback", () => {
  it("serves /health as ok JSON", () => {
    const res = handleFallback("GET", "/health", new URLSearchParams());
    expect(res.status).toBe(200);
    expect(res.body).toEqual({ status: "ok", database: "connected", scrape_busy: false });
  });

  it("serves dataset-summary with active listings", () => {
    const res = handleFallback("GET", "/api/analytics/dataset-summary", new URLSearchParams());
    expect(res.status).toBe(200);
    expect(res.body.active_listing_count).toBe(LISTINGS.length);
    expect(res.body.snapshot_state_label_cs).toMatch(/Vercel/);
  });

  it("pages listings with numeric ids", () => {
    const res = handleFallback("GET", "/api/listings", new URLSearchParams("page=1&page_size=5"));
    expect(res.status).toBe(200);
    expect(res.body.items).toHaveLength(5);
    expect(res.body.total).toBe(LISTINGS.length);
    expect(res.body.items[0].id).toBe(101);
    expect(res.body.items[0].title).toContain("Praha");
  });

  it("rejects writes while Railway is down", () => {
    const res = handleFallback("POST", "/api/scraping/trigger", new URLSearchParams());
    expect(res.status).toBe(503);
    expect(res.body.detail).toMatch(/Railway/);
  });

  it("rejects export while Railway is down", () => {
    const res = handleFallback("GET", "/api/export/listings", new URLSearchParams());
    expect(res.status).toBe(503);
  });
});

describe("isRailwayMiss", () => {
  it("treats Hikari Application not found as a miss", () => {
    expect(isRailwayMiss(404, { status: "error", code: 404, message: "Application not found" })).toBe(true);
  });

  it("does not treat a listings 200/404 payload as a miss", () => {
    expect(isRailwayMiss(200, { items: [], total: 0 })).toBe(false);
    expect(isRailwayMiss(404, { items: [] })).toBe(false);
    expect(isRailwayMiss(404, { active_listing_count: 0 })).toBe(false);
  });
});
