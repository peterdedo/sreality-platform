import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";
import { probeBackendReachability, type BackendReachability } from "../api/connectivity";

type BackendStatusContextValue = {
  /** True when production probe detected missing or unreachable backend. */
  backendUnavailable: boolean;
  /** Reason from the last failed probe (production only). */
  unavailableReason: "not_configured" | "database_unavailable" | "down" | "timeout" | null;
  checking: boolean;
  retry: () => void;
};

const BackendStatusContext = createContext<BackendStatusContextValue>({
  backendUnavailable: false,
  unavailableReason: null,
  checking: false,
  retry: () => undefined,
});

const RECHECK_INTERVAL_MS = 60_000;

export function BackendStatusProvider({ children }: PropsWithChildren) {
  const isProduction = import.meta.env.PROD;
  const [reachability, setReachability] = useState<BackendReachability>(
    isProduction ? { state: "checking" } : { state: "available" }
  );

  const runProbe = useCallback(async () => {
    if (!isProduction) {
      setReachability({ state: "available" });
      return;
    }
    setReachability({ state: "checking" });
    const result = await probeBackendReachability();
    setReachability(result);
  }, [isProduction]);

  useEffect(() => {
    void runProbe();
    if (!isProduction) return undefined;

    const intervalId = window.setInterval(() => {
      void runProbe();
    }, RECHECK_INTERVAL_MS);

    return () => window.clearInterval(intervalId);
  }, [isProduction, runProbe]);

  const value = useMemo<BackendStatusContextValue>(() => {
    const unavailable =
      isProduction && reachability.state === "unavailable" ? reachability : null;

    return {
      backendUnavailable: unavailable != null,
      unavailableReason: unavailable?.reason ?? null,
      checking: isProduction && reachability.state === "checking",
      retry: () => {
        void runProbe();
      },
    };
  }, [isProduction, reachability, runProbe]);

  return <BackendStatusContext.Provider value={value}>{children}</BackendStatusContext.Provider>;
}

export function useBackendStatus(): BackendStatusContextValue {
  return useContext(BackendStatusContext);
}

/** Hide per-widget API errors when a global backend banner already explains the outage. */
export function useSuppressConnectivityErrors(): boolean {
  const { backendUnavailable } = useBackendStatus();
  return import.meta.env.PROD && backendUnavailable;
}
