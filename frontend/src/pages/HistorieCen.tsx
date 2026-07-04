import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { PageContainer } from "../components/layout/PageContainer";
import { PriceChart } from "../components/charts/PriceChart";
import { ErrorState, LoadingState } from "../components/StateHelpers";
import { useAsync } from "../hooks/useAsync";
import { cs } from "../locale/cs";

export function HistorieCen() {
  const [searchParams] = useSearchParams();
  const [listingId, setListingId] = useState<string>("");

  useEffect(() => {
    const fromUrl = searchParams.get("id");
    if (fromUrl) setListingId(fromUrl);
  }, [searchParams]);

  const { data, loading, error } = useAsync(
    () => (listingId ? api.priceEvolution(Number(listingId), 365) : Promise.resolve([])),
    [listingId]
  );

  return (
    <PageContainer title={cs.nav.historieCenTitulek} subtitle={cs.historie.podtitulek}>
      <p className="text-xs text-ink-muted mb-4 max-w-2xl leading-relaxed">{cs.historie.navUpozorneni}</p>
      <div className="panel-static mb-4">
        <label className="field-label">{cs.detail.historieCenLabel}</label>
        <input
          type="number"
          className="input-field w-48"
          placeholder={cs.detail.historieCenPlaceholder}
          value={listingId}
          onChange={(e) => setListingId(e.target.value)}
        />
        <p className="text-xs text-ink-muted mt-2 max-w-xl leading-relaxed">{cs.detail.historieCenNapoveda}</p>
        <Link to="/nabidky" className="link-subtle text-sm inline-block mt-2">
          {cs.detail.historieCenOdkazNabidky}
        </Link>
      </div>

      <div className="panel-static">
        {!listingId && (
          <p className="text-ink-muted text-sm mb-4">{cs.detail.historieCenNapoveda}</p>
        )}
        {listingId && loading && <LoadingState />}
        {error && <ErrorState message={error.message} />}
        {listingId && !loading && !error && data && data.length === 0 && (
          <p className="text-ink-muted text-sm">{cs.common.zadnaData}</p>
        )}
        {listingId && data && data.length > 0 && <PriceChart data={data} />}
      </div>
    </PageContainer>
  );
}
