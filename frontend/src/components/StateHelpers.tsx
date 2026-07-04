import { cs } from "../locale/cs";

export function LoadingState() {
  return (
    <div className="loading-block">
      <div className="loading-block__icon" aria-hidden />
      <span className="loading-shimmer loading-shimmer--wide" />
      <span className="loading-block__text">{cs.common.nacitani}</span>
    </div>
  );
}

export function ErrorState({ message }: { message?: string }) {
  const isTimeout = Boolean(message && /neodpov[?i]d|timeout|vypr?el/i.test(message));

  return (
    <div className="status-banner status-banner--error status-banner--emphasis text-center py-10 my-2">
      <p className="font-semibold">{message ?? cs.common.chyba}</p>
      {isTimeout && (
        <p className="mt-2 text-sm opacity-80">
          Backend je dočasně přetížený nebo probíhá scraping. Zkuste stránku za chvíli obnovit.
        </p>
      )}
    </div>
  );
}

export function EmptyState({ message }: { message?: string }) {
  return (
    <div className="empty-state">
      <div className="empty-state__icon" aria-hidden />
      <p>{message ?? cs.common.zadnaData}</p>
    </div>
  );
}
