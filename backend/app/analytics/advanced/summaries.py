"""Full-dataset aggregate summaries for advanced analytics (truth layer)."""

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Listing, ListingAnomaly, ListingValuation


def valuation_summary(session: Session) -> dict:
    """Counts over all stored valuations for active listings."""
    base = (
        select(ListingValuation.classification, func.count(ListingValuation.id))
        .join(Listing, Listing.id == ListingValuation.listing_id)
        .where(Listing.is_active == True)  # noqa: E712
        .group_by(ListingValuation.classification)
    )
    by_class = {row[0] or "unclassified": row[1] for row in session.exec(base).all()}
    total = sum(by_class.values())
    return {
        "total_valued_listings": total,
        "by_classification": by_class,
    }


def anomaly_summary(session: Session, min_score: float = 0) -> dict:
    """Counts over all stored anomaly scores (full recompute output)."""
    stmt = (
        select(ListingAnomaly)
        .join(Listing, Listing.id == ListingAnomaly.listing_id)
        .where(Listing.is_active == True, ListingAnomaly.anomaly_score >= min_score)  # noqa: E712
    )
    rows = session.exec(stmt).all()
    flag_counts: dict[str, int] = {}
    for row in rows:
        for flag in row.anomaly_flags or []:
            flag_counts[flag] = flag_counts.get(flag, 0) + 1
    return {
        "total_scored_listings": session.exec(
            select(func.count(ListingAnomaly.id))
            .join(Listing, Listing.id == ListingAnomaly.listing_id)
            .where(Listing.is_active == True)  # noqa: E712
        ).one(),
        "matching_min_score": len(rows),
        "min_score": min_score,
        "flag_counts": flag_counts,
    }
