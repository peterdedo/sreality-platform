import { writeFileSync } from "node:fs";

const backend = (process.env.BACKEND_URL ?? "").replace(/\/$/, "");
const rewrites = [];

if (backend) {
  rewrites.push(
    { source: "/api/:path*", destination: `${backend}/api/:path*` },
    { source: "/health", destination: `${backend}/health` }
  );
}

rewrites.push({ source: "/((?!api/).*)", destination: "/index.html" });

writeFileSync("vercel.json", `${JSON.stringify({ rewrites }, null, 2)}\n`);
console.log(backend ? `vercel.json: proxy /api -> ${backend}` : "vercel.json: SPA only (BACKEND_URL unset)");
