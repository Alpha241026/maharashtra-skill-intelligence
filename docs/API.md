# API Contract

## Maharashtra Skill Intelligence Platform — MVP

This document defines the initial FastAPI contract between the backend and frontend.

The API is intentionally small so that the team can complete the first working vertical slice quickly.

---

# 1. Base URL

Development:

```text
http://localhost:8000
```

All application endpoints use the `/api` prefix.

Example:

```text
GET /api/districts
```

---

# 2. API Principles

- FastAPI owns HTTP/API concerns.
- PostgreSQL is the source of persistent structured data.
- React consumes JSON from FastAPI.
- AI/ML modules remain separate from FastAPI business/API code.
- The chatbot is accessed through a stable `/api/chat` contract.
- AI/ML implementation details should not leak into frontend code.
- Do not expose unsupported skill-gap claims through the API.

---

# 3. Endpoint Overview

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/districts` | List available districts |
| GET | `/api/sectors` | List available sectors |
| GET | `/api/demand` | District-sector projected training demand |
| GET | `/api/iti/supply` | ITI supply by district |
| POST | `/api/chat` | Query the grounded chatbot |

These are the initial MVP endpoints.

---

# 4. GET /api/districts

Returns the available districts.

## Request

```http
GET /api/districts
```

No request body.

## Response

```json
{
  "districts": [
    {
      "id": 1,
      "name": "Pune"
    },
    {
      "id": 2,
      "name": "Nashik"
    }
  ]
}
```

## Response fields

### `districts`

Array of district objects.

### District object

```text
id      integer
name    string
```

---

# 5. GET /api/sectors

Returns the available sectors.

## Request

```http
GET /api/sectors
```

No request body.

## Response

```json
{
  "sectors": [
    {
      "id": 1,
      "name": "Construction"
    },
    {
      "id": 2,
      "name": "Agriculture"
    }
  ]
}
```

## Response fields

### `sectors`

Array of sector objects.

### Sector object

```text
id      integer
name    string
```

---

# 6. GET /api/demand

Returns projected training demand by sector for a selected district.

This is the **primary dashboard endpoint and first vertical slice**.

## Request

```http
GET /api/demand?district=Pune
```

### Query parameter

| Parameter | Type | Required | Description |
|---|---|---|---|
| `district` | string | Yes | Maharashtra district name |

Example:

```text
/api/demand?district=Pune
```

---

## Response

```json
{
  "district": "Pune",
  "sectors": [
    {
      "sector": "Construction",
      "projected_training": 179.87,
      "demand_band": "Moderate",
      "evidence_confidence": 0.83
    }
  ]
}
```

---

## Sector demand object

```text
sector                 string
projected_training     number
demand_band            string
evidence_confidence    number
```

### `projected_training`

Model-derived projected training requirement.

### `demand_band`

Current model output classification:

```text
High
Moderate
Low
```

Current model thresholds:

```text
>= 500       High
100–499.99   Moderate
< 100        Low
```

These are project/model classifications and are **not official government classifications**.

### `evidence_confidence`

Confidence/evidence value associated with the underlying district-sector record.

---

## Backend flow

```text
GET /api/demand?district=Pune
            ↓
       validate district
            ↓
        PostgreSQL
            ↓
   district-sector records
            ↓
ProjectedTrainingIntelligence
            ↓
       model prediction
            ↓
        JSON response
```

The frontend does not call the ML module directly.

---

# 7. GET /api/iti/supply

Returns ITI training supply for a district.

## Request

```http
GET /api/iti/supply?district=Pune
```

### Query parameter

| Parameter | Type | Required | Description |
|---|---|---|---|
| `district` | string | Yes | Maharashtra district name |

---

## Response

```json
{
  "district": "Pune",
  "total_intake": 10688,
  "trades": [
    {
      "trade": "Electrician (NSQF)",
      "intake": 1280
    },
    {
      "trade": "Fitter",
      "intake": 960
    }
  ]
}
```

The exact values must be calculated from PostgreSQL rather than hardcoded.

---

## Trade supply object

```text
trade       string
intake      integer
```

### `total_intake`

Total ITI intake returned for the selected district according to the imported source data.

### `intake`

Trade-level intake aggregated from `iti_offerings`.

---

## Backend flow

```text
GET /api/iti/supply?district=Pune
            ↓
       validate district
            ↓
        PostgreSQL
            ↓
       ITI institutes
            +
       ITI offerings
            ↓
      aggregate by trade
            ↓
        JSON response
```

---

# 8. POST /api/chat

Provides access to the grounded AI chatbot.

The AI module remains separate from FastAPI.

## Request

```http
POST /api/chat
Content-Type: application/json
```

Body:

```json
{
  "question": "What skills are in demand in Pune for Construction?"
}
```

---

# 9. Chat Request Schema

```text
question    string
```

`question` is required.

---

# 10. Chat Response

The backend should preserve the AI engine's existing response structure rather than redesigning it.

The current engine returns:

```text
query
status
matched_district
matched_sector
answer
details
```

Example:

```json
{
  "query": "What skills are in demand in Pune for Construction?",
  "status": "success",
  "matched_district": "Pune",
  "matched_sector": "Construction",
  "answer": "In Pune, the projected training requirement for the Construction sector is estimated at about 180 trainees (Moderate Demand Band) (Data coverage: 83%).",
  "details": {
    "district": "Pune",
    "sector": "Construction",
    "status": "success",
    "predicted_projected_training": 179.87,
    "demand_band": "Moderate",
    "evidence_confidence": 0.83
  }
}
```

The exact `answer` and `details` values are generated by the AI module.

---

# 11. Chat Backend Flow

```text
React
  │
  │ POST /api/chat
  │ {"question": "..."}
  ↓
FastAPI
  │
  ↓
GroundedChatbotEngine
  │
  ↓
bot.ask(question)
  │
  ↓
dict result
  │
  ↓
FastAPI JSON response
  │
  ↓
React
```

FastAPI should not duplicate the chatbot's reasoning logic.

---

# 12. AI Module Boundary

The AI module is imported by the backend.

Conceptually:

```python
from engines.chatbot.chatbot_engine import GroundedChatbotEngine

bot = GroundedChatbotEngine()

result = bot.ask(question)
```

The API layer is responsible for:

- accepting HTTP requests
- validating request data
- calling the AI engine
- returning JSON
- handling HTTP-level errors

The AI module remains responsible for:

- query interpretation
- district/sector matching
- AI/ML inference
- grounded response generation
- its existing data processing

Do not modify the AI logic merely to fit the API.

---

# 13. HTTP Error Behaviour

Initial MVP behaviour:

## 400 — Invalid request

Use when required request data is missing or malformed.

Example:

```json
{
  "detail": "Question is required"
}
```

## 404 — Resource not found

Use when a requested district does not exist.

Example:

```json
{
  "detail": "District not found"
}
```

## 500 — Internal server error

Use for unexpected backend/runtime failures.

Do not expose internal stack traces to the frontend.

---

# 14. Empty Results

If a valid district exists but no matching data is available, return a successful response with an empty collection rather than inventing data.

Example:

```json
{
  "district": "Example District",
  "sectors": []
}
```

Similarly:

```json
{
  "district": "Example District",
  "total_intake": 0,
  "trades": []
}
```

The frontend can display an appropriate "No data available" state.

---

# 15. First Vertical Slice

The first integration target is:

```text
PostgreSQL
    ↓
FastAPI
    ↓
GET /api/demand?district=Pune
    ↓
JSON
    ↓
React
    ↓
Dashboard component
```

The first frontend component should consume the real API rather than permanently relying on mock data.

---

# 16. Initial Frontend Usage

Example:

```javascript
const response = await fetch(
  "http://localhost:8000/api/demand?district=Pune"
);

const data = await response.json();
```

The frontend should use the response structure defined in this document.

Do not make the frontend depend on PostgreSQL directly.

---

# 17. CORS

During local development, FastAPI should allow the frontend development origin to access the API.

Development architecture:

```text
React development server
        ↓
      FastAPI
        ↓
    PostgreSQL
```

CORS configuration should be added when the frontend begins making real requests.

Do not use unrestricted production CORS as a final deployment setting.

---

# 18. Current MVP Non-Goals

Do not add API endpoints for:

- user registration
- login
- OTP
- password reset
- employer accounts
- trainer accounts
- admin RBAC
- course recommendation
- job application
- student profiles
- equipment management
- advanced forecasting
- definitive skill-shortage calculation

unless the team explicitly adds the corresponding feature and data.

---

# 19. Future Extensions

Possible future endpoints, only if supported by validated data:

```text
GET /api/districts/{district}/overview
GET /api/alignment
GET /api/trades
GET /api/trades/{trade}
GET /api/recommendations
GET /api/emerging-skills
```

These are **NOT** part of the current MVP contract.

---

# 20. Contract Ownership

### Backend owns

- endpoint implementation
- request validation
- response schema
- database queries
- error handling

### Frontend owns

- API consumption
- loading states
- error states
- visual presentation

### AI/ML owns

- AI/data-processing logic
- model inference
- chatbot logic

### Database work owns

- PostgreSQL schema
- data import/seed process
- query correctness
- database integrity

Changes to the API response shape should be communicated to the frontend before implementation changes are merged.

---

# 21. Current Contract Summary

```text
GET  /api/districts
     → available districts

GET  /api/sectors
     → available sectors

GET  /api/demand?district={district}
     → projected training demand by sector

GET  /api/iti/supply?district={district}
     → ITI supply by trade

POST /api/chat
     → grounded AI chatbot response
```

This is the MVP API contract.

Keep it stable while the first vertical slice is being implemented.