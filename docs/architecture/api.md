# Backend API

All endpoints are prefixed with `/api/v2`. Authentication via Cognito JWT unless noted.

Module layout matches `src/app/`:

```
app.include_router(auth_router,   prefix="/v2/auth")
app.include_router(offers_router, prefix="/v2/offers")
app.include_router(user_router,   prefix="/v2/user")
```

## Conventions

| Rule          | Value                                       |
| ------------- | ------------------------------------------- |
| Auth header   | `Authorization: Bearer <cognito_jwt>`       |
| Content-Type  | `application/json`                          |
| Error format  | `{ "detail": "..." }` (FastAPI default)     |
| Pagination    | Cursor-based (`cursor`, `limit`)            |
| Rate limiting | Redis-backed custom Rate Limiter dependency |

## Auth — `/v2/auth`

Sign up and sign in happen in the PWA via Cognito directly. Only account deletion goes through the backend. On sign-up confirmation, a Cognito **post-confirmation** trigger provisions the backend `Users` record (default preferences), activates default market cells, and schedules the first match — so there is no client-facing "create account" endpoint. A lazy get-or-create on the first authenticated request is the fallback.

### `DELETE /v2/auth/account`

Delete the authenticated user's account.

**Side effects:**

1. Delete Cognito user.
2. Delete `Users` record.
3. Delete all `UserOffers` for user.
4. Decrement market cell `activation_count` for user's cells.
5. Delete Redis keys `user:{id}:*`.

**Response:** `204 No Content`

---

## User — `/v2/user`

### `GET /v2/user/preferences`

Return current preferences.

**Response `200`:**

```json
{
  "countries": ["GR", "IT", "ES", "TR", "EG"],
  "departure_airports": [],
  "date_from": null,
  "date_to": null,
  "adults": 2,
  "children": [],
  "board": "all-inclusive",
  "min_stars": 2,
  "min_rating": 0,
  "duration_min": 5,
  "duration_max": null
}
```

### `PATCH /v2/user/preferences`

Update preferences. Saves immediately; triggers a debounced match via EventBridge Scheduler.

**Request body:** partial update (same fields as GET).

**Response `200`:** full preferences object.

**Side effects:** market cell activation updated; one-time schedule `match-{user_id}` upserted for `at(now + 15s)` (see [pipeline.md](pipeline.md#preference-debouncing-eventbridge-scheduler)).

### `POST /v2/user/push/enable`

Register Web Push subscription.

**Request:**

```json
{
  "subscription": {
    "endpoint": "...",
    "keys": { "p256dh": "...", "auth": "..." }
  }
}
```

**Response:** `204 No Content`

### `POST /v2/user/push/disable`

Disable push notifications.

**Response:** `204 No Content`

---

## Offers — `/v2/offers`

Read-only feed. No per-offer seen tracking.

### `GET /v2/offers`

Paginated, sortable offer list. Served from Redis (lazy sort ZSET) with DynamoDB hydration.

**Query parameters:**

| Param    | Default          | Values                                                                                   |
| -------- | ---------------- | ---------------------------------------------------------------------------------------- |
| `sort`   | `attractiveness` | `attractiveness`, `departure_date`, `price_total`, `price_per_day`, `rating`, `duration` |
| `order`  | `desc`           | `asc`, `desc`                                                                            |
| `limit`  | `20`             | 1–50                                                                                     |
| `cursor` | —                | Opaque cursor from previous response                                                     |

**Response `200`:**

```json
{
  "offers": [
    {
      "offer_id": "a1b2c3...",
      "hotel_name": "Kakkos Terra Blue",
      "country": "Greece",
      "location": "Greece/Crete/Ierapetra",
      "departure_airport": "WAW",
      "departure_date": "2026-04-26",
      "return_date": "2026-05-03",
      "duration": 7,
      "board": "all-inclusive",
      "stars": 5,
      "rating": 4.2,
      "review_count": 544,
      "price_total": 6148,
      "referral_url": "https://...",
      "image_url": "https://i.wakacje.pl/no-index/hotel/...",
      "share_url": "https://wakacje-travelis.pl/offer/a1b2c3.../a1b2c3...",
      "favorited": false
    }
  ],
  "next_cursor": "eyJzY29yZSI6...",
  "feed_version": 42,
  "total_count": 125
}
```

`feed_version` lets the client detect feed changes (e.g. for in-app "new offers" badge). `total_count` indicates the total number of matched offers in the user's feed.

### `GET /v2/offers/{offer_id}`

Single offer detail for an offer in the user's feed.

**Behavior**: The backend looks up the `cell_id` associated with this `offer_id` in the `UserOffers` table for the authenticated user. If a match exists, it retrieves the offer from the `Offers` table using `(cell_id, offer_id)`.

**Response `200`:**

```json
{
  "offer_id": "a1b2c3...",
  "provider": "wakacje_pl",
  "external_offer_id": "916232",
  "hotel_name": "Kakkos Terra Blue",
  "country": "Greece",
  "region": "Crete",
  "location": "Greece/Crete/Ierapetra",
  "departure_airport": "WAW",
  "departure_date": "2026-04-26",
  "return_date": "2026-05-03",
  "duration": 7,
  "board": "all-inclusive",
  "stars": 5,
  "rating": 4.2,
  "review_count": 544,
  "price_total": 6148,
  "price_per_day": 439,
  "attractiveness_score": 0.92,
  "available": true,
  "referral_url": "https://...",
  "image_url": "https://i.wakacje.pl/no-index/hotel/...",
  "share_url": "https://wakacje-travelis.pl/offer/cell123/a1b2c3...",
  "favorited": false,
  "sources": [
    {
      "provider": "wakacje_pl",
      "external_offer_id": "916232",
      "price_total": 6148,
      "tour_operator": "Grecos"
    },
    {
      "provider": "wakacje_pl",
      "external_offer_id": "916240",
      "price_total": 6350,
      "tour_operator": "Itaka"
    }
  ],
  "scraped_at": "2026-04-20T06:00:00Z",
  "updated_at": "2026-04-20T06:00:00Z"
}
```

**Response `404`:** offer not in user's feed or does not exist.

### `GET /v2/offers/favorites`

Retrieve a list of the authenticated user's favorited offers.

**Query parameters:**

| Param    | Default | Values                               |
| -------- | ------- | ------------------------------------ |
| `limit`  | `20`    | 1–50                                 |
| `cursor` | —       | Opaque cursor from previous response |

**Response `200`:**
Same response schema as `GET /v2/offers` (returns a paginated list of favorited offers).

---

### `PUT /v2/offers/{offer_id}/favorite`

Mark an offer as favorited by the authenticated user.

**Query parameters:**

| Param     | Required | Description                                                                                         |
| --------- | -------- | --------------------------------------------------------------------------------------------------- |
| `cell_id` | No       | The market cell ID of the offer. Required if the offer is not currently in the user's matched feed. |

**Response `204`:** No Content

**Response `400`:** `cell_id` is missing and the offer is not in the user's matched feed (required for shared offer favoriting).

**Response `404`:** Offer detail not found in DB.

---

### `DELETE /v2/offers/{offer_id}/favorite`

Remove an offer from the authenticated user's favorites.

**Behavior**: If the offer is still in the user's matched feed, the `favorited` attribute is set to `false`. If the offer is no longer matched by preferences, the `UserOffers` row is deleted immediately.

**Response `204`:** No Content

**Response `404`:** Offer is not favorited or does not exist.

---

### `GET /v2/offers/{cell_id}/{offer_id}`

Single offer detail by cell and offer ID. Used for shared offer lookups (e.g. from the custom `share_url` format `/offer/{cell_id}/{offer_id}`). Does not require the offer to be in the calling user's personal matched feed.

**Behavior**: Fetches directly from the `Offers` table using `(cell_id, offer_id)`. Can be queried by unauthenticated requests (if sharing is public) or authenticated requests.

**Response `200`:** Same response schema as `GET /v2/offers/{offer_id}` above.

**Response `404`:** offer does not exist (expired or invalid).

---

## System

### `GET /v2/health`

**Response `200`:**

```json
{ "status": "ok" }
```

No authentication required.

## Middleware & Rate Limiting

The API implements three security and resource management layers:

1. **CORS:** Restricts API consumption to whitelisted origins (e.g. the PWA).
2. **JWT Validation:** Verifies AWS Cognito JWT tokens on protected routers.
3. **Redis-backed Rate Limiting:** Enforces route-level request limits using a custom, fail-open rate limiter.

If a client exceeds their limit, the API returns a `429 Too Many Requests` response with a `Retry-After` header indicating the cooldown period in seconds.

### Identifier Tracking

- **Authenticated Requests:** Identified by the Cognito `sub` (User ID) claim extracted from the `Authorization` header.
- **Unauthenticated/Public Requests:** Identified by the client's host IP address.

### Configured Rate Limits

| Endpoint Group           | Route                                                                           | Rate Limit   | Identified By |
| ------------------------ | ------------------------------------------------------------------------------- | ------------ | ------------- |
| **Authentication**       | `DELETE /v2/auth/account`                                                       | 3 / minute   | User ID       |
| **User Preferences**     | `GET /v2/user/preferences`<br>`PATCH /v2/user/preferences`                      | 10 / minute  | User ID       |
| **User Notifications**   | `POST /v2/user/push/enable`<br>`POST /v2/user/push/disable`                     | 10 / minute  | User ID       |
| **Offers Feed**          | `GET /v2/offers`                                                                | 100 / minute | User ID       |
| **Offer Details**        | `GET /v2/offers/{offer_id}`                                                     | 100 / minute | User ID       |
| **Favorites Feed**       | `GET /v2/offers/favorites`                                                      | 100 / minute | User ID       |
| **Favorite Action**      | `PUT /v2/offers/{offer_id}/favorite`<br>`DELETE /v2/offers/{offer_id}/favorite` | 50 / minute  | User ID       |
| **Shared Offer Details** | `GET /v2/offers/{cell_id}/{offer_id}`                                           | 60 / minute  | Client IP     |
| **System**               | `GET /v2/health`                                                                | No Limit     | —             |

## HTTP status codes

| Code  | Usage                       |
| ----- | --------------------------- |
| `200` | Successful read or update   |
| `204` | Successful delete / no body |
| `400` | Validation error            |
| `401` | Missing or invalid JWT      |
| `404` | Resource not found          |
| `429` | Rate limited                |
| `500` | Internal error              |
