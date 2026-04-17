# 🌐 AI Early Conflict Warning System

A production-ready, full-stack geopolitical tension detection system powered by NLP, anomaly detection, and real-time news analysis.

---

## 🎯 What it does

Analyzes news articles, extracts military/conflict keywords, scores sentiment, and generates:
- ⚠️ **Risk Score** (0–100) per region
- 🤖 **AI-generated alert text**
- 📈 **Sentiment timeline charts**
- 🗺️ **Interactive world risk map**
- 🔑 **Keyword cloud** of conflict indicators

---

## 🏗️ Project Structure

```
early warning system/
├── backend/
│   ├── main.py             # FastAPI application (all endpoints)
│   ├── analyzer.py         # NLP pipeline (spaCy NER, TextBlob sentiment, keyword extraction)
│   ├── risk_scorer.py      # Z-score + Isolation Forest risk scoring
│   ├── alert_generator.py  # Template-driven alert text generation
│   ├── data_ingestion.py   # NewsAPI + mock dataset fallback
│   ├── cache.py            # In-memory TTL cache (5 min)
│   └── requirements.txt
├── frontend/
│   ├── index.html          # Entry point (loads React, Chart.js, Leaflet via CDN)
│   ├── app.js              # Complete React dashboard
│   └── styles.css          # Full design system (dark glassmorphism)
├── data/
│   └── mock_news.json      # 60+ mock articles covering 7 regions
└── README.md
```

---

## 🚀 Quick Start

### Step 1: Install Python Dependencies

```powershell
cd "c:\Users\Praneet Hegde\OneDrive\Desktop\early warning system\backend"
pip install -r requirements.txt
```

### Step 2: Download spaCy Language Model (run once)

```powershell
python -m spacy download en_core_web_sm
```

### Step 3: Start the Backend

```powershell
cd "c:\Users\Praneet Hegde\OneDrive\Desktop\early warning system\backend"
uvicorn main:app --reload --port 8000
```

The API will be live at: **http://localhost:8000**
Interactive docs: **http://localhost:8000/docs**

### Step 4: Open the Frontend

Open this file directly in your browser (no build step needed):
```
c:\Users\Praneet Hegde\OneDrive\Desktop\early warning system\frontend\index.html
```

> **Note**: Chrome/Edge may block localhost requests from `file://`. If so, serve the frontend via a simple HTTP server:
> ```powershell
> cd "c:\Users\Praneet Hegde\OneDrive\Desktop\early warning system\frontend"
> python -m http.server 3000
> ```
> Then open: **http://localhost:3000**

---

## 🔑 Optional: NewsAPI Integration

To use real news data instead of the mock dataset:

1. Get a free API key at https://newsapi.org
2. Create a `.env` file in the `backend/` folder:
   ```
   NEWSAPI_KEY=your_api_key_here
   ```
3. Restart the backend

Without a key, the system automatically uses the local mock dataset (60+ articles, 7 regions).

---

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check + API info |
| `/regions` | GET | List available regions |
| `/analyze?region=...` | GET | Full NLP + risk pipeline for a region |
| `/alerts?limit=10` | GET | Ranked alerts for all regions |
| `/data?region=...` | GET | Raw article statistics |
| `/cache` | DELETE | Clear the analysis cache |
| `/docs` | GET | Interactive Swagger UI |

---

## 🧠 AI/ML Pipeline

```
News Articles
    ↓
NER (spaCy)          → Extracts countries, organizations
Sentiment (TextBlob) → Per-article polarity (-1 to +1)
Keyword Extraction   → 70+ military keywords with tier weights
    ↓
Z-Score Anomaly      → Is keyword density unusual?
Isolation Forest     → Which articles are statistical outliers?
    ↓
Composite Risk Score:
  0.4 × Sentiment Anomaly
  0.4 × Keyword Spike Score
  0.2 × Article Volume
    ↓
Risk Score (0–100) + Confidence + Alert Text
```

---

## 🌐 Regions Covered

- South China Sea
- Taiwan
- Russia-Ukraine
- Middle East (Iran, Israel)
- India-Pakistan
- Korean Peninsula
- Horn of Africa

---

## 🎨 Frontend Features

- **Dark glassmorphism UI** with animated elements
- **SVG risk gauge** with smooth arc animation
- **Chart.js** sentiment timeline and component bar chart
- **Leaflet** interactive world map with pulsing risk markers
- **Keyword cloud** with tier-weighted color coding
- **Real-time clock** and backend status indicator
- **Fully responsive** (mobile-friendly)

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|----------|
| Backend | FastAPI (Python) |
| NLP | spaCy (en_core_web_sm) + TextBlob |
| ML | scikit-learn (Isolation Forest) + NumPy |
| Data | Mock JSON + NewsAPI (optional) |
| Frontend | React 18 (CDN) + Vanilla CSS |
| Charts | Chart.js 4 |
| Map | Leaflet.js + CartoDB Dark tiles |
| Cache | In-memory TTL dict |
