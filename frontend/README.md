# Maharashtra Skill Intelligence Platform — Frontend Architecture (V1)

## Overview & Product North Star

The **Maharashtra Skill Intelligence Platform** is a government decision-support system designed for regional planning officers, vocational coordinators, and skill development authorities under the Department of Skill Development, Employment and Entrepreneurship (Government of Maharashtra).

The guiding design principle for this system is **"Calm Intelligence"**:
- **Institutional & Trustworthy:** Presents information with the clarity and authority of a serious state planning system, avoiding the superficial aesthetics of consumer SaaS landing pages.
- **Information-First:** Influenced by the **International Typographic Style (Swiss design)** and **Bauhaus geometry**—prioritizing layout grids, high contrast, typographic hierarchy, alignment, and information density over decorative noise.
- **Anti-Vibecode Standard:** Absolutely zero purple gradients, dot grids, floating blob animations, pill soup, glassmorphism, fake counters, or decorative emojis. Every visual element has a functional purpose.

---

## V1 File Inventory

```
frontend/
├── index.html        # Semantic HTML5 dashboard (accessible, single H1, structured sections)
├── login.html        # Official Departmental Login Gateway (Credentials & WebAuth/SSO socket)
├── css/
│   └── style.css     # CSS Custom Properties design system (tokens, layout, typography, states, auth)
├── js/
│   ├── app.js        # Deterministic Vanilla JS interaction layer (schema-compliant data mapping)
│   └── auth.js       # Authentication Service & WebAuth / Google OAuth 2.0 Sockets
├── assets/           # Reserved for official emblems and iconography
└── README.md         # Technical architecture & integration documentation
```

### Prototype Authentication Clearance
- **Access Route:** `http://localhost:3000/login.html`
- **Officer User ID:** `admin`
- **Password:** `SIH2026`
- **Web Authentication Sockets:**
  - `Google OAuth 2.0 / GIS Socket`: Interactive socket handler (`window.SIHAuth.loginWithGoogleSocket()`) with mock profile fallback.
  - `Hardware Token / WebAuthn`: FIDO2 biometric and security key socket (`window.SIHAuth.loginWithWebAuthn()`).


---

## Future Feature-Chunk Architecture & React Migration

During **V3 (React Migration)** and **V4 (Tailwind CSS Migration)**, this single-page static structure decomposes cleanly into independent feature chunks:

```
src/
├── app/
│   ├── App.jsx                       # Main shell & global layout
│   └── main.jsx
├── chunks/
│   ├── dashboard/                    # Header & District Snapshot context
│   │   ├── DashboardHeader.jsx
│   │   ├── DistrictSelector.jsx
│   │   └── DistrictSnapshot.jsx
│   ├── demand/                       # Projected Training Demand module
│   │   ├── DemandPanel.jsx
│   │   ├── SectorDemandRow.jsx
│   │   ├── demand.api.js             # Calls GET /api/demand?district=<name>
│   │   └── demand.utils.js
│   ├── iti/                          # ITI Supply & Capacity module
│   │   ├── ITISupplyPanel.jsx
│   │   └── iti.api.js                # Calls GET /api/iti/supply?district=<name>
│   ├── intelligence/                 # District Socio-Economic Intelligence module
│   │   ├── IntelligencePanel.jsx
│   │   └── intelligence.api.js
│   └── chatbot/                      # Grounded Conversational AI Assistant
│       ├── Chatbot.jsx
│       └── chatbot.api.js            # Calls POST /api/chat
├── services/
│   └── api.js                        # Base HTTP client (reads VITE_API_BASE_URL, fallback http://localhost:8000)
└── styles/
    └── tokens.css
```

---

## API Contract Compliance

The frontend strictly honors the API contracts documented in `docs/API.md`:

| Feature Area | Endpoint | HTTP Method | Data Owner | Frontend Representation |
| :--- | :--- | :--- | :--- | :--- |
| District List | `/api/districts` | `GET` | Backend (FastAPI) | Populates `<select id="district-select">` |
| Sector Master | `/api/sectors` | `GET` | Backend (FastAPI) | Reference sector taxonomy |
| Projected Demand | `/api/demand?district={name}` | `GET` | ML Service / FastAPI | Sector list with index, band, & confidence |
| ITI Supply | `/api/iti/supply?district={name}` | `GET` | PostgreSQL / FastAPI | ITI intake seats & capacity utilization |
| AI Chatbot | `/api/chat` | `POST` | GroundedChatbotEngine | Verified conversational synthesis |

### Data Interpretation Rules
1. **Demand Metric:** Figures represent **"Projected Training Demand"** or **"Projected Training Requirement"** at the `district + sector` level.
2. **Prohibited Claims:** The frontend **must never** claim "exact skill shortages," "unemployment counts," or "guaranteed job placements."
3. **ITI Supply:** Described as "training capacity," "sanctioned seats," or "training supply."

---

## UX State Management Matrix

Every data-driven panel is built with an explicit UX state strategy:

| State | Purpose | Visual Implementation |
| :--- | :--- | :--- |
| **Default** | Initial interactive state prior to interaction | Cleanly loaded baseline for `Pune` with contextual explanation. |
| **Loading** | User initiated action in progress | Contextual skeleton or progress indicator. **No fake progress percentages.** |
| **Success** | Data fetched and validated | Structured tabular rows, tabular numbers, CSS proportion bars. |
| **Empty** | Valid query returns zero records | Inline notice explaining missing data with a reset/retry action. |
| **Error** | API or network service failure | Inline non-intrusive error banner with recovery button. (No modal locks or raw stack traces). |
| **Partial Failure** | One module fails while others succeed | ITI panel fails independently; Demand panel remains completely operational. |
| **Disabled** | Action unavailable due to missing prerequisite | Clear visual cue explaining the prerequisite. |

---

## Team Ownership & Separation of Concerns

To allow 6 team members to work asynchronously:

- **Frontend Engineers (You):** Own visual design system, HTML semantics, CSS tokens, responsive views, UX state handling, and client-side API consumption.
- **Backend Engineers:** Own FastAPI routes, Pydantic request/response validation, error codes, and business services.
- **Database Specialists:** Own PostgreSQL schemas, table indices, migrations, and MSSDS/ITI data import pipelines.
- **AI / ML Engineers:** Own the econometric training demand models, confidence calibration, and the `GroundedChatbotEngine`.

> **Fundamental Rule:** The frontend never connects directly to PostgreSQL, CSV files, or Python ML model objects. All data passes through the documented FastAPI endpoints.

---

## Step-by-Step Staged Roadmap

- **V1 (Current):** Vanilla HTML + CSS + JS static prototype with calm intelligence styling, district selection, and schema-compliant data mapping.
- **V2:** Enhanced interaction, keyboard accessibility polish, and comprehensive state mockups.
- **V3:** Component migration to React (feature chunks: `chunks/dashboard`, `chunks/demand`, `chunks/iti`, etc.).
- **V4:** Migration of CSS custom properties to Tailwind CSS utility classes.
- **V5:** Connection of FastAPI endpoints with centralized `services/api.js`.
- **V6:** Integration of live PostgreSQL data persistence.
- **V7:** Integration of Grounded AI Skill Assistant (`POST /api/chat`).
- **V8:** Advanced intelligence filters and comparative district analytics.

---

## How to Run V1 Locally

Because V1 uses no build steps or npm packages, it can be run using any static web server:

```bash
# Using Python built-in server (from workspace root)
python -m http.server 3000 --directory frontend

# Or using Node http-server / npx serve (if available)
npx serve frontend

# Or simply open frontend/index.html in any modern browser.
```
