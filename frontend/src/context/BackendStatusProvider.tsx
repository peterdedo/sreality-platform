import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";
import {
  probeBackendReachability,
  probeScrapeBusy,
  type BackendReachability,
} from "../api/connectivity";

type BackendStatusContextValue = {
  /** True when production probe detected missing or unreachable backend. */
  backendUnavailable: boolean;
  /** Reason from the last failed probe (production only). */
  unavailableReason: "not_configured" | "database_unavailable" | "down" | "timeout" | null;
  /** True when /health reports scrape_busy (advisory lock held). */
  scrapeBusy: boolean;
  checking: boolean;
  retry: () => void;
};

const BackendStatusContext = createContext<BackendStatusContextValue>({
  backendUnavailable: false,
  unavailableReason: null,
  scrapeBusy: false,
  checking: false,
  retry: () => undefined,
});

const RECHECK_INTERVAL_MS = 60_000;
const SCRAPE_BUSY_POLL_MS = 20_000;

export function BackendStatusProvider({ children }: PropsWithChildren) {
  const isProduction = import.meta.env.PROD;
  const [reachability, setReachability] = useState<BackendReachability>(
    isProduction ? { state: "checking" } : { state: "available", scrapeBusy: false }
  );
  const [scrapeBusy, setScrapeBusy] = useState(false);

  const runProbe = useCallback(async () => {
    if (!isProduction) {
      setReachability({ state: "available", scrapeBusy: false });
      return;
    }
    setReachability({ state: "checking" });
    const result = await probeBackendReachability();
    setReachability(result);
    if (result.state === "available") {
      setScrapeBusy(result.scrapeBusy);
    }
  }, [isProduction]);

  const runScrapeBusyProbe = useCallback(async () => {
    const busy = await probeScrapeBusy();
    setScrapeBusy(busy);
  }, []);

  useEffect(() => {
    void runProbe();
    void runScrapeBusyProbe();

    const scrapeIntervalId = window.setInterval(() => {
      void runScrapeBusyProbe();
    }, SCRAPE_BUSY_POLL_MS);

    if (!isProduction) {
      return () => window.clearInterval(scrapeIntervalId);
    }

    const intervalId = window.setInterval(() => {
      void runProbe();
    }, RECHECK_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
      window.clearInterval(scrapeIntervalId);
    };
  }, [isProduction, runProbe, runScrapeBusyProbe]);

  const value = useMemo<BackendStatusContextValue>(() => {
    const unavailable =
      isProduction && reachability.state === "unavailable" ? reachability : null;

    return {
      backendUnavailable: unavailable != null,
      unavailableReason: unavailable?.reason ?? null,
      scrapeBusy,
      checking: isProduction && reachability.state === "checking",
      retry: () => {
        void runProbe();
        void runScrapeBusyProbe();
      },
    };
  }, [isProduction, reachability, runProbe, runScrapeBusyProbe, scrapeBusy]);

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
