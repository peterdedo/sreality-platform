import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

function resolveApiProxyTarget(env: Record<string, string>) {
  if (env.VITE_API_PROXY_TARGET) {
    return env.VITE_API_PROXY_TARGET;
  }
  // WSL2 forwards port 8000 to Windows localhost — more stable than a dynamic WSL IP.
  return "http://localhost:8000";
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiProxyTarget = resolveApiProxyTarget(env);

  return {
    plugins: [react()],
    server: {
      host: true,
      port: env.PORT ? Number(env.PORT) : 5173,
      strictPort: Boolean(env.PORT),
      proxy: {
        "/api": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
