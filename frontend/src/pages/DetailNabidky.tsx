import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { PageContainer } from "../components/layout/PageContainer";
import { SrealityLink } from "../components/SrealityLink";
import { ErrorState, LoadingState } from "../components/StateHelpers";
import { PriceChart } from "../components/charts/PriceChart";
import { ComparablesPanel } from "../components/advanced/ComparablesPanel";
import { useAsync } from "../hooks/useAsync";
import { cs } from "../locale/cs";
import { DEAL_TYPES, PROPERTY_TYPES, formatCzk, formatDate } from "../constants";

export function DetailNabidky() {
  const { id } = useParams<{ id: string }>();
  const listingId = Number(id);
  const { data, loading, error } = useAsync(() => api.listingDetail(listingId), [listingId]);

  return (
    <PageContainer title={cs.detail.titulek}>
      <Link to="/nabidky" className="btn-ghost !px-0 mb-4 inline-flex">
        ← {cs.detail.zpet}
      </Link>

      {loading && <LoadingState />}
      {error && <ErrorState message={error.message} />}

      {data && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            <div className="panel-static">
              <h2 className="text-xl font-semibold text-navy mb-1">{data.listing.title}</h2>
              <p className="text-ink-muted text-sm mb-4">
                {PROPERTY_TYPES[data.listing.category_main_cb]} · {DEAL_TYPES[data.listing.category_type_cb]}
              </p>
              <p className="text-2xl font-bold text-ink mb-4">{formatCzk(data.listing.price_czk)}</p>
              {data.listing.source_url && (
                <SrealityLink
                  href={data.listing.source_url}
                  className="link-brand inline-flex items-center mb-4"
                >
                  {cs.detail.odkazSreality} ↗
                </SrealityLink>
              )}
              {data.description && <p className="text-ink whitespace-pre-line">{data.description}</p>}
            </div>

            <div className="panel-static">
              <h3 className="panel__title !mb-3">{cs.detail.historieCen}</h3>
              <PriceChart data={data.price_history} />
            </div>

            <div className="panel-static">
              <h3 className="panel__title !mb-3">{cs.advanced.srovnatelne.titulek}</h3>
              <ComparablesPanel listingId={data.listing.id} />
            </div>
          </div>

          <div className="space-y-4">
            <div className="panel-static text-sm space-y-2">
              <Row label={cs.detail.plochaUzitna} value={data.usable_area ? `${data.usable_area} m²` : null} />
              <Row label={cs.detail.podlazi} value={data.floor} />
              <Row label={cs.detail.vlastnictvi} value={data.ownership} />
              <Row label={cs.detail.typBudovy} value={data.building_type} />
              <Row label={cs.detail.stavBudovy} value={data.building_condition} />
              <Row label={cs.detail.energetickyStitek} value={data.energy_efficiency_rating} />
              <Row label={cs.detail.vybaveni} value={data.furnished} />
              <Row label={cs.detail.vytah} value={data.elevator} />
              <Row label={cs.detail.zahrada} value={data.garden === null ? null : data.garden ? cs.listings.ano : cs.listings.ne} />
              <Row label={cs.detail.makler} value={data.broker_company} />
              <Row label={cs.detail.poznamkaKCene} value={data.note_about_price} />
              <Row label={cs.common.posledniAktualizace} value={formatDate(data.listing.last_seen_at)} />
            </div>

            {data.images.length > 0 && (
              <div className="grid grid-cols-2 gap-2">
                {data.images.slice(0, 6).map((url) => (
                  <img key={url} src={url} alt="" className="rounded-md object-cover aspect-square" />
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </PageContainer>
  );
}

function Row({ label, value }: { label: string; value: string | number | null }) {
  return (
    <div className="flex justify-between border-b border-surface-border pb-2 last:border-0">
      <span className="text-ink-muted">{label}</span>
      <span className="font-medium text-ink">{value ?? "—"}</span>
    </div>
  );
}
