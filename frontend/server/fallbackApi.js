/** Offline demo payload so the Vercel SPA stays usable when Railway is down. */

const NOW = "2026-10-06T08:00:00.000Z";
const WEEK_AGO = "2026-09-29T08:00:00.000Z";
const MONTH_AGO = "2026-09-06T08:00:00.000Z";

function listing(partial) {
  const area = partial.usable_area ?? 72;
  const price = partial.price_czk ?? 6_500_000;
  return {
    hash_id: String(partial.id),
    category_main_cb: 1,
    category_type_cb: 1,
    category_sub_cb: 4,
    price_per_m2: Math.round(price / area),
    gps_lat: partial.gps_lat,
    gps_lon: partial.gps_lon,
    is_active: true,
    first_seen_at: MONTH_AGO,
    last_seen_at: NOW,
    last_updated_at: NOW,
    removed_at: null,
    source_url: `https://www.sreality.cz/detail/prodej/byt/2+kk/${partial.id}`,
    seller_type: "realitni kancelar",
    usable_area: area,
    floor_area: area,
    land_area: null,
    floor: `${partial.floor_number ?? 3}. podlaží`,
    floor_number: partial.floor_number ?? 3,
    total_floors: 6,
    ownership: "osobní",
    building_type: "cihlová",
    building_condition: "velmi dobrý",
    energy_efficiency_rating: "C",
    furnished: "částečně",
    elevator: "ano",
    balcony: true,
    terrace: false,
    cellar: true,
    garage: false,
    garden: false,
    parking_lots: 0,
    days_on_market: 30,
    price_change_count: partial.price_change_count ?? 0,
    has_price_drop: Boolean(partial.has_price_drop),
    image_count: 4,
    description_length: 420,
    ...partial,
    price_czk: price,
  };
}

export const LISTINGS = [
  listing({ id: 101, title: "Prodej bytu 2+kk, Praha 3 - Žižkov", locality_text: "Praha 3 - Žižkov", region: "Hlavní město Praha", district: "Praha 3", city: "Praha", gps_lat: 50.087, gps_lon: 14.451, price_czk: 7_890_000, usable_area: 58, has_price_drop: true, price_change_count: 1 }),
  listing({ id: 102, title: "Prodej bytu 3+1, Praha 5 - Smíchov", locality_text: "Praha 5 - Smíchov", region: "Hlavní město Praha", district: "Praha 5", city: "Praha", gps_lat: 50.075, gps_lon: 14.401, price_czk: 11_200_000, usable_area: 86, floor_number: 5 }),
  listing({ id: 103, title: "Prodej bytu 2+1, Brno - střed", locality_text: "Brno-střed", region: "Jihomoravský kraj", district: "Brno-město", city: "Brno", gps_lat: 49.195, gps_lon: 16.608, price_czk: 6_150_000, usable_area: 64 }),
  listing({ id: 104, title: "Prodej bytu 1+kk, Brno - Královo Pole", locality_text: "Brno-Královo Pole", region: "Jihomoravský kraj", district: "Brno-město", city: "Brno", gps_lat: 49.226, gps_lon: 16.596, price_czk: 4_290_000, usable_area: 38, floor_number: 2 }),
  listing({ id: 105, title: "Prodej bytu 3+kk, Ostrava - Poruba", locality_text: "Ostrava-Poruba", region: "Moravskoslezský kraj", district: "Ostrava-město", city: "Ostrava", gps_lat: 49.828, gps_lon: 18.171, price_czk: 3_850_000, usable_area: 78, has_price_drop: true, price_change_count: 2 }),
  listing({ id: 106, title: "Prodej bytu 2+kk, Plzeň - Jižní Předměstí", locality_text: "Plzeň", region: "Plzeňský kraj", district: "Plzeň-město", city: "Plzeň", gps_lat: 49.747, gps_lon: 13.377, price_czk: 4_620_000, usable_area: 55 }),
  listing({ id: 107, title: "Prodej bytu 4+1, Olomouc", locality_text: "Olomouc", region: "Olomoucký kraj", district: "Olomouc", city: "Olomouc", gps_lat: 49.594, gps_lon: 17.251, price_czk: 5_740_000, usable_area: 92, floor_number: 4 }),
  listing({ id: 108, title: "Prodej bytu 2+kk, Liberec", locality_text: "Liberec", region: "Liberecký kraj", district: "Liberec", city: "Liberec", gps_lat: 50.767, gps_lon: 15.056, price_czk: 3_980_000, usable_area: 52 }),
  listing({ id: 109, title: "Prodej bytu 3+kk, Hradec Králové", locality_text: "Hradec Králové", region: "Královéhradecký kraj", district: "Hradec Králové", city: "Hradec Králové", gps_lat: 50.21, gps_lon: 15.832, price_czk: 5_150_000, usable_area: 74 }),
  listing({ id: 110, title: "Prodej bytu 2+1, České Budějovice", locality_text: "České Budějovice", region: "Jihočeský kraj", district: "České Budějovice", city: "České Budějovice", gps_lat: 48.975, gps_lon: 14.475, price_czk: 4_480_000, usable_area: 61 }),
];

const ACTIVE = LISTINGS.length;

export function healthBody() {
  return { status: "ok", database: "connected", scrape_busy: false };
}

export function handleFallback(method, pathname, searchParams) {
  const path = pathname.replace(/\/$/, "") || "/";

  if (path === "/health" || path === "/api/health") {
    return { status: 200, body: healthBody() };
  }

  if (method !== "GET") {
    return {
      status: 503,
      body: {
        detail:
          "Zápis (scraping, export, přepočet) vyžaduje Railway backend. Ten teď nemá aktivní deployment — v projektu vivacious-wholeness klikněte Deploy/Restart.",
      },
    };
  }

  if (path === "/api/analytics/dataset-summary") {
    return {
      status: 200,
      body: {
        data_scope: "fallback",
        active_listing_count: ACTIVE,
        total_listing_count: ACTIVE,
        active_with_gps_count: ACTIVE,
        active_with_region_count: ACTIVE,
        active_with_detail_count: ACTIVE,
        active_with_valuation_count: 6,
        active_with_anomaly_count: 2,
        active_without_gps_count: 0,
        active_without_region_count: 0,
        inventory_region_listing_sum: ACTIVE,
        last_successful_scrape_at: NOW,
        last_full_sweep_at: NOW,
        last_full_sweep_items_seen: ACTIVE,
        dataset_completeness: "complete",
        dataset_freshness: "final_partial",
        active_category_slice_count: 1,
        expected_category_slice_count: 1,
        running_scrape: null,
        running_detail_backfill: null,
        snapshot_state_label_cs: "Dočasná data na Vercel (Railway API není dostupné)",
        compare_guidance_cs:
          "Produkční Railway backend teď neodpovídá. Dashboard ukazuje 10 ukázkových nabídek, aby šlo UI používat. Po Deploy/Restart v Railway se sem vrátí plný dataset.",
        is_count_final: true,
        safe_to_compare_with_sreality_total: false,
        last_dataset_update_at: NOW,
        needs_region_backfill: false,
      },
    };
  }

  if (path === "/api/listings/map-markers") {
    const items = LISTINGS.map((l) => ({
      id: l.id,
      gps_lat: l.gps_lat,
      gps_lon: l.gps_lon,
      price_czk: l.price_czk,
      title: l.title,
      category_main_cb: l.category_main_cb,
      category_type_cb: l.category_type_cb,
      source_url: l.source_url,
    }));
    return { status: 200, body: { items, total: items.length, truncated: false } };
  }

  if (path === "/api/listings/location-suggest") {
    const q = (searchParams.get("q") ?? "").trim().toLowerCase();
    const seen = new Set();
    const items = [];
    for (const l of LISTINGS) {
      const label = [l.city, l.district, l.region].filter(Boolean).join(", ");
      if (q && !label.toLowerCase().includes(q) && !(l.locality_text ?? "").toLowerCase().includes(q)) continue;
      const key = l.city ?? label;
      if (seen.has(key)) continue;
      seen.add(key);
      items.push({ label, region: l.region, district: l.district, city: l.city, municipality: l.city });
      if (items.length >= Number(searchParams.get("limit") ?? 15)) break;
    }
    return { status: 200, body: { items } };
  }

  if (path === "/api/listings/municipalities") {
    const region = searchParams.get("region");
    const counts = new Map();
    for (const l of LISTINGS) {
      if (region && l.region !== region) continue;
      const name = l.city ?? "—";
      counts.set(name, (counts.get(name) ?? 0) + 1);
    }
    const items = [...counts.entries()].map(([municipality, listing_count]) => ({ municipality, listing_count }));
    return { status: 200, body: { items } };
  }

  const listingDetail = path.match(/^\/api\/listings\/(\d+)$/);
  if (listingDetail) {
    const row = LISTINGS.find((l) => l.id === Number(listingDetail[1]));
    if (!row) return { status: 404, body: { detail: "Nabídka nenalezena" } };
    return {
      status: 200,
      body: {
        listing: row,
        description: `${row.title}. Ukázková nabídka zobrazená, protože produkční Railway API momentálně neodpovídá.`,
        usable_area: row.usable_area,
        floor_area: row.floor_area,
        floor: row.floor,
        ownership: row.ownership,
        building_type: row.building_type,
        building_condition: row.building_condition,
        energy_efficiency_rating: row.energy_efficiency_rating,
        furnished: row.furnished,
        elevator: row.elevator,
        balcony: row.balcony,
        terrace: row.terrace,
        loggia: false,
        cellar: row.cellar,
        garage: row.garage,
        garden: row.garden,
        parking_lots: row.parking_lots,
        broker_company: "Ukázková kancelář",
        note_about_price: null,
        images: [],
        price_history: row.has_price_drop
          ? [
              { price_czk: Math.round((row.price_czk ?? 0) * 1.06), recorded_at: MONTH_AGO },
              { price_czk: row.price_czk, recorded_at: WEEK_AGO },
            ]
          : [{ price_czk: row.price_czk, recorded_at: MONTH_AGO }],
      },
    };
  }

  if (path === "/api/listings") {
    const page = Math.max(1, Number(searchParams.get("page") ?? 1));
    const pageSize = Math.min(100, Math.max(1, Number(searchParams.get("page_size") ?? 25)));
    let rows = LISTINGS.filter((l) => (searchParams.get("is_active") === "false" ? !l.is_active : l.is_active));
    const region = searchParams.get("region");
    if (region) rows = rows.filter((l) => l.region === region);
    const start = (page - 1) * pageSize;
    return {
      status: 200,
      body: { items: rows.slice(start, start + pageSize), total: rows.length, page, page_size: pageSize },
    };
  }

  if (path === "/api/analytics/inventory-by-region") {
    const counts = new Map();
    for (const l of LISTINGS) counts.set(l.region, (counts.get(l.region) ?? 0) + 1);
    const items = [...counts.entries()].map(([region, listing_count]) => ({ region, listing_count }));
    return { status: 200, body: { items, listing_count_sum: ACTIVE, data_scope: "fallback" } };
  }

  if (path === "/api/analytics/new-vs-removed") {
    return { status: 200, body: { new_count: 3, removed_count: 1, period_days: Number(searchParams.get("days") ?? 30), data_scope: "fallback" } };
  }

  if (path === "/api/analytics/price-drops") {
    const dropped = LISTINGS.filter((l) => l.has_price_drop).map((l) => ({
      listing_id: l.id,
      title: l.title,
      previous_price_czk: Math.round((l.price_czk ?? 0) * 1.06),
      current_price_czk: l.price_czk,
      drop_pct: 6,
    }));
    const limit = searchParams.get("limit") ? Number(searchParams.get("limit")) : dropped.length;
    return { status: 200, body: { items: dropped.slice(0, limit), total_matched: dropped.length, limit } };
  }

  if (path === "/api/analytics/price-per-m2") {
    const byRegion = new Map();
    for (const l of LISTINGS) {
      const cur = byRegion.get(l.region) ?? { sum: 0, n: 0, p2: 0 };
      cur.sum += l.price_czk ?? 0;
      cur.p2 += l.price_per_m2 ?? 0;
      cur.n += 1;
      byRegion.set(l.region, cur);
    }
    const items = [...byRegion.entries()].map(([region, v]) => ({
      region,
      district: null,
      municipality: null,
      avg_price_czk: Math.round(v.sum / v.n),
      avg_price_per_m2: Math.round(v.p2 / v.n),
      listing_count: v.n,
    }));
    return { status: 200, body: { items } };
  }

  if (path === "/api/analytics/price-evolution") {
    const listingId = searchParams.get("listing_id");
    const rows = listingId ? LISTINGS.filter((l) => l.id === Number(listingId)) : LISTINGS.slice(0, 1);
    const items = rows.flatMap((l) => [
      { listing_id: l.id, price_czk: Math.round((l.price_czk ?? 0) * 1.04), recorded_at: MONTH_AGO },
      { listing_id: l.id, price_czk: l.price_czk, recorded_at: NOW },
    ]);
    return { status: 200, body: { items } };
  }

  if (path === "/api/analytics/count-reconciliation") {
    return { status: 200, body: { active_listing_count: ACTIVE, data_scope: "fallback" } };
  }

  if (path === "/api/scraping/runs") {
    return {
      status: 200,
      body: [
        {
          id: 1,
          run_type: "incremental",
          category: "Byty - Prodej",
          status: "success",
          started_at: MONTH_AGO,
          finished_at: NOW,
          pages_fetched: 1,
          items_seen: ACTIVE,
          items_new: ACTIVE,
          items_updated: 0,
          items_removed: 0,
          error_count: 0,
          error_message: "Railway backend není dostupný — zobrazená data jsou dočasný fallback na Vercel.",
        },
      ],
    };
  }

  if (/^\/api\/scraping\/runs\/\d+\/items$/.test(path)) {
    return { status: 200, body: [] };
  }

  if (path.startsWith("/api/export")) {
    return {
      status: 503,
      body: {
        detail:
          "Export vyžaduje Railway backend. Ten teď nemá aktivní deployment — v projektu vivacious-wholeness klikněte Deploy/Restart.",
      },
    };
  }

  if (path === "/api/analytics/advanced/market-dynamics") {
    const items = [
      {
        id: 1,
        snapshot_date: MONTH_AGO.slice(0, 10),
        location_id: null,
        category_main_cb: 1,
        category_type_cb: 1,
        listing_count: 8,
        avg_price_czk: 5_800_000,
        median_price_czk: 5_150_000,
        avg_price_per_m2: 82_000,
        new_count: 2,
        removed_count: 1,
        median_days_on_market: 28,
        avg_days_on_market: 31,
        price_drop_share: 0.2,
        median_first_to_last_price_change_pct: -3.1,
      },
      {
        id: 2,
        snapshot_date: NOW.slice(0, 10),
        location_id: null,
        category_main_cb: 1,
        category_type_cb: 1,
        listing_count: ACTIVE,
        avg_price_czk: 5_733_000,
        median_price_czk: 5_150_000,
        avg_price_per_m2: 83_400,
        new_count: 3,
        removed_count: 1,
        median_days_on_market: 30,
        avg_days_on_market: 30,
        price_drop_share: 0.2,
        median_first_to_last_price_change_pct: -4.2,
      },
    ];
    return { status: 200, body: { items } };
  }

  if (path === "/api/analytics/advanced/segments") {
    const items = [...new Map(LISTINGS.map((l) => [l.region, l])).values()].map((l) => ({
      value: l.region,
      label: l.region,
      listing_count: LISTINGS.filter((x) => x.region === l.region).length,
      avg_price_czk: l.price_czk,
      avg_price_per_m2: l.price_per_m2,
    }));
    return { status: 200, body: { items, listing_count_sum: ACTIVE, data_scope: "fallback" } };
  }

  if (path === "/api/analytics/advanced/valuation/summary") {
    return {
      status: 200,
      body: {
        data_scope: "fallback",
        total_valued_listings: 6,
        by_classification: { under_market: 2, near_market: 3, over_market: 1 },
      },
    };
  }

  if (path === "/api/analytics/advanced/valuation") {
    const items = LISTINGS.slice(0, 6).map((l, i) => ({
      id: i + 1,
      listing_id: l.id,
      model_id: 1,
      expected_price_czk: Math.round((l.price_czk ?? 0) * 1.02),
      expected_price_per_m2: l.price_per_m2,
      residual_absolute: Math.round((l.price_czk ?? 0) * -0.02),
      residual_percent: -2,
      classification: i === 0 || i === 4 ? "under_market" : i === 5 ? "over_market" : "near_market",
      confidence: "medium",
      computed_at: NOW,
    }));
    return { status: 200, body: { items, total: items.length, limit: items.length, offset: 0, data_scope: "fallback" } };
  }

  const valuationDetail = path.match(/^\/api\/analytics\/advanced\/valuation\/(\d+)$/);
  if (valuationDetail) {
    const listingId = Number(valuationDetail[1]);
    const l = LISTINGS.find((row) => row.id === listingId);
    if (!l) return { status: 404, body: { detail: "Nenalezeno" } };
    return {
      status: 200,
      body: {
        id: listingId,
        listing_id: listingId,
        model_id: 1,
        expected_price_czk: Math.round((l.price_czk ?? 0) * 1.02),
        expected_price_per_m2: l.price_per_m2,
        residual_absolute: Math.round((l.price_czk ?? 0) * -0.02),
        residual_percent: -2,
        classification: "near_market",
        confidence: "medium",
        computed_at: NOW,
      },
    };
  }

  if (path === "/api/analytics/advanced/anomalies/summary") {
    return {
      status: 200,
      body: {
        data_scope: "fallback",
        total_scored_listings: ACTIVE,
        matching_min_score: 2,
        min_score: Number(searchParams.get("min_score") ?? 0),
        flag_counts: { price_drop: 2, duplicate: 0 },
      },
    };
  }

  if (path === "/api/analytics/advanced/anomalies") {
    const items = LISTINGS.filter((l) => l.has_price_drop).map((l, i) => ({
      id: i + 1,
      listing_id: l.id,
      anomaly_score: 0.62,
      anomaly_flags: ["price_drop"],
      confidence_score: 0.7,
      computed_at: NOW,
    }));
    return { status: 200, body: { items, total: items.length, limit: items.length, offset: 0, data_scope: "fallback" } };
  }

  const comparables = path.match(/^\/api\/analytics\/advanced\/comparables\/(\d+)$/);
  if (comparables) {
    const listingId = Number(comparables[1]);
    const others = LISTINGS.filter((l) => l.id !== listingId).slice(0, 4);
    return {
      status: 200,
      body: {
        listing_id: listingId,
        comparables: others.map((l) => ({
          listing_id: l.id,
          title: l.title,
          price_czk: l.price_czk,
          price_per_m2: l.price_per_m2,
          distance_km: 4.2,
        })),
        median_comparable_price_czk: others[0]?.price_czk ?? null,
        median_comparable_price_per_m2: others[0]?.price_per_m2 ?? null,
        deviation_from_comparables_pct: -3.4,
        note: "Fallback srovnání (Railway API není dostupné).",
      },
    };
  }

  if (path === "/api/analytics/advanced/spatial/heatmap") {
    const items = LISTINGS.map((l) => ({
      grid_id: `${l.id}`,
      lat_center: l.gps_lat,
      lon_center: l.gps_lon,
      listing_count: 1,
      avg_price_per_m2: l.price_per_m2,
      price_drop_intensity: l.has_price_drop ? 0.4 : 0,
      turnover_rate: 0.1,
    }));
    return {
      status: 200,
      body: {
        items,
        grid_step_degrees: 0.05,
        bbox_applied: false,
        cell_count: items.length,
        aggregated: false,
        source: "live",
      },
    };
  }

  if (path === "/api/analytics/advanced/runs") {
    return {
      status: 200,
      body: [
        {
          id: 1,
          run_type: "recompute",
          status: "success",
          started_at: MONTH_AGO,
          finished_at: NOW,
          items_processed: ACTIVE,
          error_count: 0,
          error_message: null,
        },
      ],
    };
  }

  return { status: 404, body: { detail: `Endpoint ${path} není v fallback API.` } };
}
