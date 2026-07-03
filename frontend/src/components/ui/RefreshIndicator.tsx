import { cs } from "../../locale/cs";

/** Inline indicator while stale data is being refreshed in the background. */
export function RefreshIndicator({ active }: { active: boolean }) {
  if (!active) return null;
  return <p className="loading-inline mb-2">{cs.common.aktualizaceDat}</p>;
}
