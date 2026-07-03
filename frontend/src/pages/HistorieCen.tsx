import { useState } from "react";
import { api } from "../api/client";
import { PageContainer } from "../components/layout/PageContainer";
import { PriceChart } from "../components/charts/PriceChart";
import { ErrorState, LoadingState } from "../components/StateHelpers";
import { useAsync } from "../hooks/useAsync";
import { cs } from "../locale/cs";

export function HistorieCen() {
  const [listingId, setListingId] = useState<string>("");
  const { data, loading, error } = useAsync(
    () => (listingId ? api.priceEvolution(Number(listingId), 365) : Promise.resolve([])),
    [listingId]
  );

  return (
    <PageContainer title={cs.detail.historieCen}>
      <div className="panel-static mb-4">
        <label className="field-label">ID nabídky</label>
        <input
          type="number"
          className="input-field w-48"
          placeholder="např. 12345"
          value={listingId}
          onChange={(e) => setListingId(e.target.value)}
        />
      </div>

      <div className="panel-static">
        {!listingId && (
          <p className="text-ink-muted text-sm mb-4">Zadejte ID nabídky pro zobrazení historie cen.</p>
        )}
        {listingId && loading && <LoadingState />}
        {error && <ErrorState message={error.message} />}
        {listingId && data && <PriceChart data={data} />}
      </div>
    </PageContainer>
  );
}
