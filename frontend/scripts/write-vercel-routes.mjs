import { writeFileSync } from "node:fs";

const backend = (process.env.BACKEND_URL ?? "").replace(/\/$/, "");

const rewrites = [];
if (backend) {
  rewrites.push(
    { source: "/api/:path*", destination: `${backend}/api/:path*` },
    { source: "/health", destination: `${backend}/health` }
  );
}
// SPA fallback — must be last; enables direct URLs like /sprava-scrapingu
rewrites.push({ source: "/(.*)", destination: "/index.html" });

const config = {
  installCommand: "node scripts/write-vercel-routes.mjs && npm install",
  buildCommand: "tsc -b && vite build",
  outputDirectory: "dist",
  rewrites,
};

writeFileSync("vercel.json", `${JSON.stringify(config, null, 2)}\n`);
console.log(backend ? `vercel.json: SPA + proxy -> ${backend}` : "vercel.json: SPA only (BACKEND_URL unset)");
