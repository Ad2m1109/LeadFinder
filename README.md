# LeadFinder

A full-stack automated lead generation tool that scrapes businesses from Google Maps, extracts contact details, analyzes websites for SEO issues, captures screenshots, and finds email addresses — all in one dashboard.

## Features

- **Google Maps Scraping** — Search by category, city, and country with Playwright-powered browser automation
- **Real-time Dashboard** — Live progress tracking with polling-based status updates
- **SEO Audit** — Automatic analysis of title tags, meta descriptions, mobile viewport, and H1 tags
- **Website Screenshots** — Playwright-captured screenshots for each business website
- **Email Finder** — Crawls business websites and contact pages to extract email addresses
- **Social Media Detection** — Identifies Instagram and Facebook profiles from Maps listings
- **Cold Email Generator** — Rule-based personalized outreach drafts based on lead data
- **Google Sheets Sync** — Auto-sync leads to a Google Sheet (with local CSV fallback)
- **CSV Export** — Download leads directly from the browser as CSV

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+, FastAPI, Uvicorn |
| Scraping | Playwright (Chromium), BeautifulSoup |
| Frontend | Next.js 16, React 19, TypeScript |
| Styling | Tailwind CSS v4 |
| Storage | Google Sheets API, local CSV |

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+ & npm
- Playwright Chromium browser (`playwright install chromium`)

### 1. Clone the repository

```bash
git clone https://github.com/Ad2m1109/LeadFinder.git
cd LeadFinder
```

### 2. Set up the backend

```bash
cd lead-finder/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 3. Configure environment

Copy and edit the `.env` file:

```bash
cp .env.example .env
```

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Backend server port | `8000` |
| `HOST` | Backend server host | `0.0.0.0` |
| `MAX_SCRAPE_RESULTS` | Max results per scrape | `50` |
| `GOOGLE_SHEET_NAME` | Google Sheet name | `Lead Finder Results` |
| `GOOGLE_CREDENTIALS_FILE` | Path to service account JSON | `credentials.json` |
| `GOOGLE_CREDENTIALS_JSON` | Inline credentials JSON string | _(empty)_ |

> **Note:** If no Google credentials are configured, LeadFinder falls back to saving leads in `backend/leads.csv`.

### 4. Start the backend

```bash
uvicorn app.main:app --reload --port 8000
```

API available at `http://localhost:8000`.

### 5. Start the frontend

```bash
cd ../frontend
npm install
npm run dev
```

Dashboard available at `http://localhost:3000`.

## API Reference

### `POST /api/search`

Start a scraping job.

```json
{
  "category": "Restaurant",
  "city": "Tirana",
  "country": "Albania",
  "max_results": 20
}
```

### `GET /api/status`

Poll the current scraping job status.

### `GET /api/leads`

Retrieve all stored leads.

### `POST /api/clear`

Clear the local CSV database.

## Google Sheets Setup (Optional)

1. Create a service account in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable **Google Sheets API** and **Google Drive API**
3. Download the credentials JSON and save as `lead-finder/backend/credentials.json`
4. Share your Google Sheet with the service account's email address

## Project Structure

```
lead-finder/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entrypoint & status manager
│   │   ├── config.py            # Environment configuration
│   │   └── services/
│   │       ├── google_maps.py   # Playwright Google Maps scraper
│   │       ├── sheet.py         # Google Sheets / CSV integration
│   │       ├── website.py       # SEO audit & screenshot capture
│   │       ├── email.py         # Email finder via web crawling
│   │       └── ai.py            # Cold email pitch generator
│   ├── .env                     # Environment variables
│   └── leads.csv                # Local lead database (auto-created)
│
└── frontend/                    # Next.js 16 dashboard
    ├── app/
    │   ├── page.tsx             # Dashboard UI
    │   ├── layout.tsx           # Root layout
    │   └── globals.css          # Tailwind CSS v4
    └── package.json
```

## License

MIT
