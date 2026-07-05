import { useBackendStatus } from "../../context/BackendStatusProvider";
import { cs } from "../../locale/cs";
import { StatusBanner } from "../ui/primitives";

export function BackendUnavailableBanner() {
  const { backendUnavailable, unavailableReason, checking, retry } = useBackendStatus();

  if (!import.meta.env.PROD || checking || !backendUnavailable) {
    return null;
  }

  const copy =
    unavailableReason === "not_configured"
      ? cs.backend.notConfigured
      : unavailableReason === "timeout"
        ? cs.backend.timeout
        : cs.backend.unavailable;

  return (
    <StatusBanner variant="warning" className="backend-unavailable-banner mx-4 mt-4 max-w-6xl lg:mx-auto">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="font-semibold">{cs.backend.title}</p>
          <p className="mt-1 text-sm opacity-90">{copy}</p>
          <p className="mt-2 text-xs opacity-75">{cs.backend.hint}</p>
        </div>
        <button type="button" className="btn-secondary shrink-0 self-start" onClick={retry}>
          {cs.backend.retry}
        </button>
      </div>
    </StatusBanner>
  );
}
