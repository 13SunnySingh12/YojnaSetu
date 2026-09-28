# YojnaSetu REST API

Public API served by the Spring Boot backend. JSON in and out. Errors are RFC 9457 problem details
(`application/problem+json`) with a human-readable `detail`; validation errors add an `errors` array.
Missing official fields are `null` in responses. When the database is unreachable, data endpoints answer **503**
("Scheme data is temporarily unavailable…") within about 5 seconds.

## Schemes

| Method and path | Purpose |
|---|---|
| `GET /api/schemes` | Keyword search and filtered browsing. Query: `q` (≤200), `category`, `state` (Indian state or UT), `gender` (`Male`/`Female`/`Transgender`), `age` (0–120), `beneficiaryType`, `level` (`Central`/`State`), `need` (key from `/api/filters`), `page` (0–500), `size` (1–50). With `q`, best text match first; otherwise by name. A state filter keeps central schemes. Returns `{items: SchemeSummary[], page, size, total}`. |
| `GET /api/schemes/{id}` | Full scheme record (all official fields, `references`, `faqs`, `eligibility`, `sourceUrl`, `sourceName`, `syncedAt`). 404 when unknown. |
| `GET /api/filters` | Filter options from stored data: `categories` (with counts), `states`, `beneficiaryTypes`, `occupations`, `needs` (`{key, label}`), `genders`, `levels`. |
| `GET /api/search?q=` | Combined keyword + meaning search (reciprocal rank fusion, de-duplicated). `q` 2–200, `page` 0–4, `size` 1–25. Items: `{scheme, matchedByKeyword, matchedByMeaning}`; `semanticAvailable: false` when only keyword results could be produced. |
| `GET /api/schemes/{id}/related` | Schemes whose overview is closest in meaning: `{items, available}`. |

## Eligibility

| Method and path | Purpose |
|---|---|
| `POST /api/eligibility/check` | Body (all optional): `age`, `state`, `gender`, `socialCategory` (`General`/`OBC`/`SC`/`ST`), `occupation`, `annualIncome` (rupees, ≥0), `schemeIds` (≤10). Deterministic comparison with stored conditions. Without `schemeIds`: a shortlist (≤50) of schemes that do not conflict with the answers, most matched conditions first. Returns `{results, likelyMatch, moreInfoNeeded, notAMatch}`; each result has `status` (`LIKELY_MATCH`/`NOT_A_MATCH`/`MORE_INFO_NEEDED`) and `matched`/`unmatched`/`missing` conditions `{field, requirement, yourValue}`. A scheme with no comparable conditions is never a likely match. |
| `POST /api/eligibility/explain` | Same body with exactly one scheme id. The server recomputes the result and returns a one- or two-sentence plain-language explanation: `{schemeId, status, explanation}`. Rate limited. |

The guidance notice is part of the client, not the API: every eligibility result must be shown with it.

## AI answers

| Method and path | Purpose |
|---|---|
| `POST /api/ask` | Body `{question (3–500), schemeId?}`. Answer written only from retrieved official scheme text: `{answer, grounded, sources: [{schemeId, name, sourceUrl}]}`. `grounded: false` means the stored data does not contain the answer. Rate limited. |
| `POST /api/schemes/{id}/explain` | Body `{section}` — one of `description`, `details`, `eligibilityText`, `benefits`, `documents`, `applicationProcess`, `conditions`. Returns `{section, original, explanation}`; `explanation` is `null` when no simpler version could be made. 404 "Not available from the official source." when the section is empty. Rate limited. |

AI endpoints answer **503** with a friendly `detail` when the AI service or providers are unavailable, and
**429** when the per-client or total rate limit is reached.

## Health

`GET /actuator/health` (with `/liveness` and `/readiness` probes).

## Internal AI service (not public)

FastAPI endpoints `POST /search`, `/related`, `/ask`, `/explain`, `/explain-eligibility` accept calls only with
the `X-Internal-Token` header matching `AI_SERVICE_TOKEN` (401 otherwise, including when the token is unset).
`GET /health` is open.
