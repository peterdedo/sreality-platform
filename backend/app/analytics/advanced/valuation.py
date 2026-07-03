"""Stage 3: interpretable fair-price model (hedonic regression).

log(price_czk) ~ log(usable_area) + category_sub_cb + building_condition +
ownership + energy_efficiency_rating + floor_number + amenities + location_grid_cell,
fit separately per (category_main_cb, category_type_cb) segment via plain
ordinary least squares (scikit-learn LinearRegression) -- not gradient
boosting. See docs/METHODOLOGY.md §3 for the full rationale, thresholds, and
explicit limitations. This is a transparent baseline, not a valuation
guarantee: coefficients and R^2 are stored in ValuationModel precisely so the
model stays inspectable rather than a black box.
"""

import math
from datetime import datetime

import pandas as pd
from sklearn.linear_model import LinearRegression
from sqlmodel import Session, select

from app.analytics.advanced.geo import grid_cell
from app.domain.floor import parse_floor_number
from app.models import (
    Listing,
    ListingDetail,
    ListingValuation,
    ValuationClassification,
    ValuationConfidence,
    ValuationModel,
)

MIN_TRAINING_SAMPLES = 30
MIN_CELL_OCCURRENCES = 3  # grid cells rarer than this collapse into "OTHER" to bound one-hot cardinality
UNDER_MARKET_THRESHOLD_PCT = -10.0
OVER_MARKET_THRESHOLD_PCT = 10.0

CATEGORICAL_DETAIL_FEATURES = ["building_condition", "ownership", "energy_efficiency_rating"]
AMENITY_FEATURES = ["balcony", "terrace", "loggia", "cellar", "garage"]


def _segment_rows(session: Session, category_main_cb: int, category_type_cb: int) -> list[dict]:
    stmt = (
        select(Listing, ListingDetail)
        .join(ListingDetail, ListingDetail.listing_id == Listing.id)
        .where(
            Listing.category_main_cb == category_main_cb,
            Listing.category_type_cb == category_type_cb,
            Listing.is_active == True,  # noqa: E712
            ListingDetail.usable_area.is_not(None),
            ListingDetail.usable_area > 0,
        )
    )
    rows = []
    for listing, detail in session.exec(stmt).all():
        cell_id = None
        if listing.gps_lat is not None and listing.gps_lon is not None:
            cell_id, _, _ = grid_cell(listing.gps_lat, listing.gps_lon)
        rows.append(
            {
                "listing_id": listing.id,
                "price_czk": listing.price_czk,
                "log_usable_area": pd.NA if not detail.usable_area else math.log(detail.usable_area),
                "usable_area": detail.usable_area,
                "category_sub_cb": str(listing.category_sub_cb),
                "floor_number": detail.floor_number if detail.floor_number is not None else parse_floor_number(detail.floor),
                "building_condition": detail.building_condition or "unknown",
                "ownership": detail.ownership or "unknown",
                "energy_efficiency_rating": detail.energy_efficiency_rating or "unknown",
                "balcony": bool(detail.balcony),
                "terrace": bool(detail.terrace),
                "loggia": bool(detail.loggia),
                "cellar": bool(detail.cellar),
                "garage": bool(detail.garage),
                "grid_cell": cell_id or "unknown",
            }
        )
    return rows


def _build_design_matrix(rows: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (feature_frame, raw_frame). Collapses rare grid cells into
    "OTHER" to keep one-hot cardinality bounded for small datasets."""
    raw = pd.DataFrame(rows)
    cell_counts = raw["grid_cell"].value_counts()
    rare_cells = cell_counts[cell_counts < MIN_CELL_OCCURRENCES].index
    raw["grid_cell_grouped"] = raw["grid_cell"].where(~raw["grid_cell"].isin(rare_cells), "OTHER")

    categorical_cols = ["category_sub_cb", *CATEGORICAL_DETAIL_FEATURES, "grid_cell_grouped"]
    numeric_cols = ["log_usable_area", "floor_number"]
    bool_cols = AMENITY_FEATURES

    features = pd.get_dummies(raw[categorical_cols], drop_first=True)
    for col in numeric_cols:
        features[col] = pd.to_numeric(raw[col], errors="coerce").fillna(raw[col].astype("float64").median())
    for col in bool_cols:
        features[col] = raw[col].astype(int)

    features = features.fillna(0.0).astype(float)
    return features, raw


def fit_and_apply_valuations(session: Session, version: str | None = None) -> list[ValuationModel]:
    """Fits one hedonic-regression model per (category_main_cb, category_type_cb)
    segment with enough training data, and writes a ListingValuation row for
    every active listing with a usable_area, using ValuationConfidence.unavailable
    for listings in segments too small to model (never a fabricated estimate)."""

    version = version or datetime.utcnow().isoformat()
    segments = session.exec(select(Listing.category_main_cb, Listing.category_type_cb).distinct()).all()

    fitted_models: list[ValuationModel] = []

    for category_main_cb, category_type_cb in sorted(set(segments)):
        rows = _segment_rows(session, category_main_cb, category_type_cb)
        segment_key = f"{category_main_cb}_{category_type_cb}"

        if len(rows) < MIN_TRAINING_SAMPLES:
            for row in rows:
                _write_valuation(
                    session,
                    listing_id=row["listing_id"],
                    model_id=None,
                    expected_price=None,
                    expected_price_per_m2=None,
                    price_czk=row["price_czk"],
                    usable_area=row["usable_area"],
                    confidence=ValuationConfidence.unavailable,
                )
            continue

        features, raw = _build_design_matrix(rows)
        y = raw["price_czk"].apply(lambda p: math.log(p) if p and p > 0 else None)
        train_mask = y.notna()

        model = LinearRegression()
        model.fit(features[train_mask], y[train_mask])
        r2 = model.score(features[train_mask], y[train_mask])

        valuation_model = ValuationModel(
            version=version,
            segment_key=segment_key,
            target="log_price_czk",
            feature_list=list(features.columns),
            coefficients=dict(zip(features.columns, [float(c) for c in model.coef_])),
            intercept=float(model.intercept_),
            r2=float(r2),
            n_samples=int(train_mask.sum()),
            trained_at=datetime.utcnow(),
            notes=(
                f"OLS on log(price_czk); {int(train_mask.sum())} training rows; "
                f"R^2={r2:.3f}. See docs/METHODOLOGY.md §3 for limitations."
            ),
        )
        session.add(valuation_model)
        session.commit()
        session.refresh(valuation_model)
        fitted_models.append(valuation_model)

        n_samples = int(train_mask.sum())
        confidence = (
            ValuationConfidence.high
            if n_samples >= 100 and r2 >= 0.4
            else ValuationConfidence.medium
            if n_samples >= MIN_TRAINING_SAMPLES
            else ValuationConfidence.low
        )

        log_predictions = model.predict(features)
        for i, row in enumerate(rows):
            expected_price = math.exp(log_predictions[i])
            _write_valuation(
                session,
                listing_id=row["listing_id"],
                model_id=valuation_model.id,
                expected_price=expected_price,
                expected_price_per_m2=expected_price / row["usable_area"] if row["usable_area"] else None,
                price_czk=row["price_czk"],
                usable_area=row["usable_area"],
                confidence=confidence,
            )

    session.commit()
    return fitted_models


def _write_valuation(
    session: Session,
    *,
    listing_id: int,
    model_id: int | None,
    expected_price: float | None,
    expected_price_per_m2: float | None,
    price_czk: int | None,
    usable_area: float | None,
    confidence: ValuationConfidence,
) -> None:
    residual_absolute = None
    residual_percent = None
    classification = None

    if expected_price and price_czk:
        residual_absolute = price_czk - expected_price
        residual_percent = residual_absolute / expected_price * 100
        if residual_percent <= UNDER_MARKET_THRESHOLD_PCT:
            classification = ValuationClassification.under_market
        elif residual_percent >= OVER_MARKET_THRESHOLD_PCT:
            classification = ValuationClassification.over_market
        else:
            classification = ValuationClassification.near_market

    existing = session.exec(select(ListingValuation).where(ListingValuation.listing_id == listing_id)).first()
    now = datetime.utcnow()
    if existing:
        existing.model_id = model_id
        existing.expected_price_czk = expected_price
        existing.expected_price_per_m2 = expected_price_per_m2
        existing.residual_absolute = residual_absolute
        existing.residual_percent = residual_percent
        existing.classification = classification
        existing.confidence = confidence
        existing.computed_at = now
        session.add(existing)
    else:
        session.add(
            ListingValuation(
                listing_id=listing_id,
                model_id=model_id,
                expected_price_czk=expected_price,
                expected_price_per_m2=expected_price_per_m2,
                residual_absolute=residual_absolute,
                residual_percent=residual_percent,
                classification=classification,
                confidence=confidence,
                computed_at=now,
            )
        )
