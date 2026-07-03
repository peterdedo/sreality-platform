import { cs } from "../../locale/cs";
import { LoadingState } from "../StateHelpers";

/** Full-page fallback while a lazy route chunk loads. */
export function PageRouteFallback() {
  return (
    <div className="page-shell" role="status" aria-live="polite">
      <LoadingState />
      <p className="sr-only">{cs.common.nacitaniStranky}</p>
    </div>
  );
}
