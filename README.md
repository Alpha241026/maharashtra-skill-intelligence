# Maharashtra Skill Intelligence Platform

**Smart India Hackathon (SIH) 2026 — Software Edition**

A district-level skill and vocational training intelligence dashboard for Maharashtra, synthesizing econometric demand projections from the Maharashtra State Skill Development Society (MSSDS) and technical training capacity from the Directorate of Vocational Education and Training (DVET).

---

## 🏛️ System Highlights

- **Pilot Baseline**: Real validated MSSDS & DVET intelligence for **Pune** (Zero Mock Data standard).
- **Projected Training Demand**: Econometric sector-wise demand modeling with confidence calibrations.
- **ITI Supply Analysis**: Comprehensive CTS trade-wise seat capacity breakdown with utilization metrics.
- **Dynamic Policy Directives**: Real-time cross-reconciliation of demand gaps and institutional capacity.
- **Grounded AI Assistant**: Retrieval-Augmented Generation (RAG) providing verifiable, evidence-backed answers.
- **Interactive V2 Design System**: Premium calm intelligence aesthetic with responsive sliding/squeezing micro-interactions and government-standard visual polish.

---

## 📁 Project Structure

```
├── backend/            # FastAPI Python intelligence backend
│   └── main.py         # REST endpoints (/api/demand, /api/iti/supply, /api/chat)
├── engines/            # ML & Chatbot RAG engines
├── data/               # Official MSSDS & DVET training and sector datasets
├── models/             # Pre-trained ML joblib models
├── frontend/           # Vanilla HTML5 / CSS3 / JavaScript dashboard
│   ├── index.html      # Main District Planning Console
│   ├── login.html      # Restricted Officer Gateway
│   ├── css/style.css   # V2 Design System with responsive micro-interactions
│   └── js/app.js       # Dynamic data binding & live API pipeline layer
├── server.js           # Lightweight Node.js server & reverse-proxy gateway
├── start.bat           # One-click Windows launch script
├── stop.bat            # One-click Windows shutdown script
└── package.json        # Project metadata and npm scripts
```

---

## 🚀 Quick Start (One-Click)

### Windows
Double-click **`start.bat`** to start both the Node.js frontend gateway and FastAPI backend simultaneously.
The dashboard will automatically open in your default browser at:
👉 **`http://localhost:3000/`**

To stop all background services, double-click **`stop.bat`**.

---

### Manual Launch

1. **Start the Frontend & Proxy Gateway**:
   ```bash
   node server.js
   ```
   *Note: `server.js` will automatically detect and start the FastAPI Python backend if not already active.*

2. **Access the Dashboard**:
   - Web Console: `http://localhost:3000/`
   - FastAPI Interactive API Docs: `http://127.0.0.1:8000/docs`