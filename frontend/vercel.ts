import { defineConfig } from "@vercel/config";

const backend = (process.env.BACKEND_URL ?? "").replace(/\/$/, "");

const rewrites: Array<{ source: string; destination: string }> = [];
if (backend) {
  rewrites.push(
    { source: "/api/:path*", destination: `${backend}/api/:path*` },
    { source: "/health", destination: `${backend}/health` }
  );
}
rewrites.push({ source: "/(.*)", destination: "/index.html" });

export default defineConfig({
  buildCommand: "tsc -b && vite build",
  outputDirectory: "dist",
  rewrites,
});
