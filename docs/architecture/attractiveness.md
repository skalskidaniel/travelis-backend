# Attractiveness Scoring

Two-stage algorithm: gate on price, then rank survivors by composite score.

## Comparison groups

Offers are statistically compared within a group defined by:

```
(country, travel_month, min_stars, board_type, adults, children)
```

This matches the global market cell dimensions. All offers scraped for a cell form the comparison pool for that run.

> **Note**: The `rating` signal used in scoring is on the canonical **0–5** scale. wakacje.pl returns ratings on a 0–10 scale; these are already divided by 2 during ingest normalization (see [agent-guidelines.md](agent-guidelines.md#8-rating-normalization)). TUI ratings are natively 0–5 and used as-is.

## Stage 1 — Price gate (deal detector)

### Metric

```
price_per_day_per_person = price_total / duration_nights / (adults + children)
```

### Z-score

Within the comparison group for the current scrape run:

```
z = (price_per_day_per_person - mean) / stddev
```

*Edge case handling*: If all offers in the comparison group have the same price, `stddev` will be `0.0`. In this case, set `z = 0.0` for all offers to avoid division by zero.

### Gate rule

An offer passes stage 1 if:

```
z <= -1.0
```

Offers cheaper than ~84% of the comparison group are kept. Configurable via SSM/env (`ATTRACTIVENESS_Z_THRESHOLD`).

### Small sample fallback

If the comparison group has **fewer than 30 offers**, Z-score is unreliable. Fallback:

- Skip Z-score gate.
- Keep the top **10%** cheapest by `price_per_day_per_person`.
- **Rounding rule**: Calculate the number of passing offers as `math.ceil(count * 0.1)`, guaranteeing that at least **1** offer always passes the gate (e.g. if there are 5 offers, `math.ceil(0.5) = 1` offer is kept).

## Stage 2 — Composite score

For offers passing stage 1, compute a weighted composite within the same comparison group.

### Signals and weights (v1)

| Signal                   | Weight | Normalization Formula                                  |
| ------------------------ | ------ | ------------------------------------------------------ |
| Price per day per person | 0.4    | `price_norm = (max_price - price) / (max_price - min_price)` |
| Rating                   | 0.4    | `rating_norm = (rating - min_rating) / (max_rating - min_rating)` |
| Review count             | 0.2    | `reviews_norm = (log_reviews - min_log_reviews) / (max_log_reviews - min_log_reviews)` |

*Note*: `log_reviews` is calculated as `math.log1p(review_count)` (natural log of `review_count + 1`).

#### Normalization Boundary Conditions (Division-by-Zero Handling)
For all three normalization steps, if the denominator evaluates to `0.0` (i.e. `max_value == min_value`), the normalized value must be set to `1.0` (as all offers in the pool are equivalent for that metric).

```
attractiveness_score = 0.4 * price_norm + 0.4 * rating_norm + 0.2 * reviews_norm
```

All normalized values mapped to `[0, 1]` where 1 is best.

The composite is **rank-only**, not a second gate. Because each signal is min-max normalized _within the group_, the score is relative — every group always contains offers near `1.0` and near `0.0` regardless of absolute quality, so a fixed absolute cutoff (e.g. `0.6`) would keep an arbitrary, group-size-dependent slice (dropping good offers in strong groups, keeping mediocre ones in weak groups). Persistence is therefore gated by **stage 1** only; the composite drives feed ordering.

If a volume cap is needed later, make it relative (top-N% / percentile) or switch stage 2 to absolute normalization (`rating/5`, log-capped reviews) so a fixed threshold becomes meaningful.

### Optional signals (future)

Not used in v1 scoring:

- Departure time
- Distance to beach
- Distance to city center
- Distance to airport
- Hotel/offer popularity (number of views)

Add in the future versions - to be done later.

### Weight calibration (future)

v1 uses fixed weights. [AHP](https://en.wikipedia.org/wiki/Analytic_hierarchy_process) may be used offline to derive updated constants; runtime always uses configured values.

## Persistence rule

Only **stage-1 passers** (the price gate) are written to the `Offers` table. There is **no per-cell quantity cap** — all qualifying attractive offers are stored. Stage 2 only assigns the ranking score.

`attractiveness_score` is stored on the offer for sorting; `price_z_score` is kept under the offer's `metadata` map for debugging.

## Worked example

Comparison group: Greece, 2026-04, 4★, all-inclusive, 2 adults, 0 children. 200 offers scraped.

| Offer | price/day/person | z    | Pass? | rating | reviews | composite |
| ----- | ---------------- | ---- | ----- | ------ | ------- | --------- |
| A     | 180 PLN          | -1.8 | ✅    | 4.5    | 500     | 0.92      |
| B     | 250 PLN          | -0.6 | ❌    | 4.8    | 1200    | —         |
| C     | 210 PLN          | -1.3 | ✅    | 3.9    | 80      | 0.71      |

Offers A and C are stored. A ranks higher in the user's feed (default sort: `attractiveness` desc).

## Dependencies

- NumPy or pandas for mean, stddev, and normalization within groups.
- Runs inside `jobs.score_offers` in the lambdalith (same Lambda as API).
