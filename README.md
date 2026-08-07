# LeetcodeInterviewHelper

LeetcodeInterviewHelper is a full-stack tool for tracking LeetCode progress and preparing for technical interviews. It syncs solved problems automatically via a browser extension, maps them onto a visual topic roadmap, diagnoses weak areas with an LLM, and runs mock interview loops modeled on real company question banks.

Live app: [leetcode-interview-helper.vercel.app](https://leetcode-interview-helper.vercel.app)

## How it fits together

The project has three parts, each in its own directory:

- **`frontend/`** — a React (Vite) single-page app. Renders the topic roadmap as an interactive graph (React Flow + Dagre), surfaces spaced-repetition reviews, AI-generated diagnoses, and problem recommendations, and drives the mock interview flow. Auth is handled via Supabase.
- **`backend/`** — a Flask API that owns all the logic: Supabase JWT verification, Postgres access (SQLAlchemy), pulling submission data from LeetCode, running diagnosis/recommendation logic, generating and evaluating mock interviews through an LLM, and spaced-repetition scheduling.
- **`leetcode-project-sync/`** — a Manifest V3 Chrome extension. Watches your LeetCode session and forwards submission activity to the backend automatically, so problems you solve on leetcode.com show up in the tracker without any manual entry.

## Core features

- **Topic roadmap** — an interactive graph of DSA topics and subpatterns, showing how thoroughly each has been practiced.
- **Automatic progress sync** — the browser extension keeps solved-problem history up to date with no manual logging.
- **AI diagnosis** — analyzes recent submissions and failure patterns to identify specific weak spots.
- **Spaced repetition** — resurfaces previously solved problems on a review schedule.
- **Recommendations** — suggests next problems based on current gaps.
- **Mock interviews** — runs single-question or full-loop mock interviews using company-specific question banks, with LLM-based evaluation of your solutions.

## Tech stack

| Layer            | Stack                                                        |
|-------------------|--------------------------------------------------------------|
| Frontend          | React, Vite, React Router, React Flow, Dagre                 |
| Backend           | Flask, SQLAlchemy, PostgreSQL, Gunicorn                      |
| Auth              | Supabase (JWT, verified against Supabase's JWKS endpoint)    |
| AI / LLM          | OpenAI API                                                   |
| Browser extension | Manifest V3 (Chrome), background service worker              |

## Running locally

### Backend

```sh
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file with the required Supabase, Postgres, and OpenAI credentials, then start the server:

```sh
flask --app app run
```

### Frontend

```sh
cd frontend
npm install
npm run dev
```

Configure `frontend/.env` with your Supabase project URL/key and the backend API URL.

### Browser extension

Load `leetcode-project-sync/` as an unpacked extension via `chrome://extensions` (Developer mode). It listens on `leetcode.com` and forwards activity to the backend URL configured in `manifest.json`.

## Project structure

```
backend/                  Flask API, auth, LLM/diagnosis logic, database access
frontend/                 React + Vite single-page app
leetcode-project-sync/    Chrome extension for automatic progress sync
```
