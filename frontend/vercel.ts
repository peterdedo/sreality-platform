import type { VercelConfig } from "@vercel/config";

/** Vercel deployment config — SPA + optional API proxy to external backend. */
export default {
  framework: "vite",
  installCommand: "npm install",
  buildCommand: "npm run build",
  outputDirectory: "dist",
  async rewrites() {
    const backend = process.env.BACKEND_URL?.replace(/\/$/, "");
    const rules: { source: string; destination: string }[] = [];

    if (backend) {
      rules.push({ source: "/api/:path*", destination: `${backend}/api/:path*` });
      rules.push({ source: "/health", destination: `${backend}/health` });
    }

    rules.push({ source: "/((?!api/).*)", destination: "/index.html" });
    return rules;
  },
} satisfies VercelConfig;
