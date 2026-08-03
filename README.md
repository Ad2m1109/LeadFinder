# LeadFinder (MVP)

A powerful full-stack automated lead generation tool that scrapes businesses from Google Maps based on category, city, and country, extracts details in real-time, and syncs them automatically to a Google Sheet (with a local CSV fallback).

## Project Structure

```
lead-finder/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI Entrypoint & Status Manager
│   │   ├── config.py          # App Configuration
│   │   ├── services/
│   │   │   ├── google_maps.py # Playwright Google Maps Scraper
│   │   │   ├── sheet.py       # Google Sheets / CSV Integration
│   │   │   ├── website.py     # Website Analyzer (Phase 2 Stub)
│   │   │   ├── email.py       # Email Finder (Phase 2 Stub)
│   │   │   └── ai.py          # AI Recommendation (Phase 2 Stub)
│   │   ├── models/            # Schema definitions
│   │   └── utils/             # Helper utilities
│   ├── .env                   # Backend environment configurations
│   └── leads.csv              # Local backup database (Auto-created)
│
└── frontend/                  # Next.js 16 (React 19) Dashboard Web App
    ├── app/
    │   ├── page.tsx           # Dashboard UI
    │   ├── layout.tsx         # Global Layout
    │   └── globals.css        # Tailwind CSS v4 setup
    ├── public/
    └── package.json
```

## Getting Started

### 1. Prerequisites
Make sure you have:
* Python 3.10+
* Node.js 18+ & npm
* Google Maps Playwright dependencies installed (`playwright install chromium`)

### 2. Configure Backend Credentials
To sync scraped leads to Google Sheets:
1. Create a service account in your Google Cloud Console.
2. Enable the **Google Sheets API** and **Google Drive API**.
3. Download the credentials JSON file and save it as `lead-finder/backend/credentials.json`.
4. Create or share a Google Sheet with your service account's client email.

*Note: If no credentials are found, LeadFinder will gracefully fallback to saving leads in `lead-finder/backend/leads.csv`.*

### 3. Running the Backend
From your terminal, navigate to the `backend` folder (make sure your virtualenv is activated) and run:
```bash
# In ~/Desktop/Projects/assistant
source .venv/bin/activate
cd lead-finder/backend
uvicorn app.main:app --reload --port 8000
```
The API server will start running at `http://localhost:8000`.

### 4. Running the Frontend
In another terminal, navigate to the `frontend` folder and run:
```bash
cd lead-finder/frontend
npm run dev
```
The dashboard web app will be available at `http://localhost:3000`.

## API Documentation

### POST `/api/search`
Triggers an asynchronous scraping run.
* **Body:**
```json
{
  "category": "Restaurant",
  "city": "Tirana",
  "country": "Albania",
  "max_results": 20
}
```
* **Response:**
```json
{
  "status": "running"
}
```

### GET `/api/status`
Retrieves progress of the currently active scraping job.
* **Response:**
```json
{
  "status": "running",
  "query": "Restaurant in Tirana, Albania",
  "leads_found": 12,
  "current_lead": {
    "name": "Restaurant A",
    "phone": "+355 4 123 4567",
    "website": "http://rest-a.al",
    "rating": 4.5,
    "reviews": 82,
    "address": "Rruga ..."
  },
  "error": null
}
```

### GET `/api/leads`
Retrieves all leads scraped and stored in the database.
* **Response:**
```json
{
  "leads": [
    {
      "name": "Restaurant A",
      "phone": "+355 4 123 4567",
      "website": "http://rest-a.al",
      "rating": 4.5,
      "reviews": 82,
      "address": "Rruga ..."
    }
  ]
}
```

### POST `/api/clear`
Clears the local CSV database.

## Roadmap & Phase 2
Once the MVP is verified, we will enable:
1. **Email Finder (`email.py`)**: Automatic web crawling to locate corporate/contact email addresses.
2. **SEO Audit (`website.py`)**: Page speed, meta tag validation, mobile responsive check.
3. **Screenshot Capture (`website.py`)**: Playwright page rendering screenshots.
4. **AI Recommender (`ai.py`)**: Automated, personalized cold outreach email scripts.
