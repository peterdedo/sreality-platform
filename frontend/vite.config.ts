import { execSync } from "node:child_process";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

function resolveApiProxyTarget() {
  if (process.env.VITE_API_PROXY_TARGET) {
    return process.env.VITE_API_PROXY_TARGET;
  }

  try {
    const wslIp = execSync(`wsl -d Ubuntu -e bash -lc "hostname -I | awk '{print $1}'"`, {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
    if (wslIp) {
      return `http://${wslIp}:8000`;
    }
  } catch {
    // Fall back to localhost for non-WSL setups.
  }

  return "http://localhost:8000";
}

const apiProxyTarget = resolveApiProxyTarget();

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: process.env.PORT ? Number(process.env.PORT) : 5173,
    strictPort: Boolean(process.env.PORT),
    proxy: {
      "/api": {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
});
