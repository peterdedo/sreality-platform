import { dispatchApi } from "../server/railwayProxy.js";
import { handleFallback } from "../server/fallbackApi.js";

export const config = { runtime: "edge" };

export default async function handler(request) {
  return dispatchApi(request, handleFallback);
}
