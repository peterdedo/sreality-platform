import { describe, expect, it } from "vitest";
import { classifyDatasetSummaryFailure } from "./connectivity";

describe("classifyDatasetSummaryFailure", () => {
  it("treats an HTML 404 as a missing Vercel API rewrite", () => {
    expect(classifyDatasetSummaryFailure(404, "text/html; charset=utf-8")).toBe("not_configured");
  });

  it("treats a JSON 404 from Railway/Vercel proxy as a down backend", () => {
    expect(classifyDatasetSummaryFailure(404, "application/json")).toBe("down");
  });

  it("treats 502/503 as a down backend", () => {
    expect(classifyDatasetSummaryFailure(502, "application/json")).toBe("down");
    expect(classifyDatasetSummaryFailure(503, "text/plain")).toBe("down");
  });
});
