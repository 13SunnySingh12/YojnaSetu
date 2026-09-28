# YojnaSetu

Government scheme finder and eligibility assistant for Indian government schemes. YojnaSetu helps citizens
discover schemes, understand eligibility rules in simple language, check likely eligibility, and read verified
scheme details — always with a link to the official government source.

> YojnaSetu gives guidance only. It does not process applications or decide eligibility; the final decision
> always belongs to the concerned government department.

Full specification: [`YojnaSetu.md`](YojnaSetu.md) · verified progress: [`Docs/Implementation/PLAN.md`](Docs/Implementation/PLAN.md)
· API reference: [`Docs/API/README.md`](Docs/API/README.md)

## Architecture

```
React (Frontend/) ──REST/JSON──> Spring Boot (Backend/) ──> MongoDB Atlas: schemes, text search, filters
                                     │  deterministic eligibility engine
                                     └──REST + internal token──> FastAPI (AI/)
                                                                   ├─ Gemini: embeddings, generation
                                                                   ├─ Groq: generation fallback
                                                                   └─ Atlas Vector Search on scheme chunks
Official sources (data.gov.in API, verified myScheme / ministry pages) ──> AI/ingestion ──> MongoDB Atlas
```

| Part | Stack | Responsibility |
|---|---|---|
| `Frontend/` | React 19, Vite, plain CSS | Search, browse, scheme detail, eligibility flow, compare, ask |
| `Backend/` | Java 21, Spring Boot 4, Maven | REST API, validation, keyword search and filters, eligibility rules, AI orchestration, rate limits |
| `AI/app` | Python 3.12, FastAPI | Semantic search, related schemes, RAG answers, plain-language explanations |
| `AI/ingestion` | Python, SQL (sqlite3) | Loads official scheme data, validates sources, chunks and embeds text |

Key rules: scheme data comes only from official Government of India sources, and every record must carry an
`https` source on a `.gov.in` / `.nic.in` host (enforced in code and by a MongoDB schema validator). Missing
fields are shown as "Not available from the official source". AI answers use only retrieved official text; with
no relevant evidence the model is not called. If the AI service is down, keyword search, scheme details and
eligibility checks keep working.

## Run locally

Prerequisites: Docker, Java 21, Maven 3.9, Python 3.12, Node.js 22.22+.

```bash
cp .env.example .env          # then fill in values; never commit .env
docker compose up -d          # Atlas Local (27018), AI service (8000), backend (8080)
cd Frontend && npm ci && npm run dev   # http://localhost:5173, proxies /api to :8080
```

`AI_SERVICE_TOKEN` must be the same random value for the backend and the AI service. Without `GEMINI_API_KEY`
/ `GROQ_API_KEY` the AI features answer "unavailable" and everything else still works.

Load official data (needs `GEMINI_API_KEY` for embeddings, and `DATA_GOV_IN_API_KEY` for data.gov.in):

```bash
cd AI
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt   # Linux/macOS: .venv/bin/pip
.venv/Scripts/python -m ingestion setup        # collections, source validator, indexes
.venv/Scripts/python -m ingestion verified     # records in ingestion/verified_schemes.json
.venv/Scripts/python -m ingestion ogd          # datasets listed in ingestion/ogd_datasets.json
```

myScheme publishes no developer API, so its scheme details are added by hand: copy each scheme from its official
page (myScheme or the ministry site) into `ingestion/verified_schemes.json`, check it against that page, and keep
the page as `sourceUrl`. Fields you leave out show as "Not available from the official source". `eligibility`
takes only `minAge`, `maxAge`, `genders`, `states`, `socialCategories`, `occupations` and `maxAnnualIncome`;
a record with a wrong type, an unknown field or a non-government link is rejected with the reason.

```json
[{"_id": "scheme-slug", "name": "Official scheme name", "sourceName": "myScheme",
  "sourceUrl": "https://www.myscheme.gov.in/schemes/scheme-slug", "level": "Central",
  "description": "…", "eligibilityText": "…", "benefits": "…", "documents": "…", "applicationProcess": "…",
  "categories": ["…"], "eligibility": {"minAge": 18, "maxAnnualIncome": 250000}}]
```

Re-running is safe: only changed text is re-embedded. The verified file is the complete list, so a scheme removed
from it is removed from the database (never when the file is empty or mostly emptied), and a verified scheme
replaces the same scheme loaded from data.gov.in.

## Tests

```bash
cd Backend && mvn verify                  # JUnit + Testcontainers (Atlas Local); needs Docker
cd AI && .venv/Scripts/python -m pytest   # unit + integration; needs `docker compose up -d mongodb`
cd Frontend && npm test && npm run lint && npm run build
```

Test fixtures and provider responses in tests are marked `MOCK / TEST ONLY`; they are never loaded into a real
database.

## Configuration

All settings are environment variables; see [`.env.example`](.env.example) for every name. Keys stay
server-side: the browser only ever talks to the Spring Boot API, and the AI service accepts calls only with the
internal token.
