# AgentMatch — Agentic Dating Demo

A hackathon prototype where each person is represented by an agent. The demo dataset contains 25 Tamil Nadu profiles with LinkedIn and public Instagram source URLs, normalized into transparent profile signals. Agents can date each other, explain shared signals, and produce a personalized ranking for every person.

## Demo flow
1. Open **People** and choose **Analyze**.
2. Show the two source links and the source-by-source profile analysis.
3. Open **Dating room**, choose two agents, and click **Start date**.
4. Click **Run all rankings** to generate a personalized ranking for every agent.
5. Open an individual ranking to show that rankings are person-specific.

## Run locally
### Backend
```bash
cd backend
python -m venv .venv
.venv\\Scripts\\activate       # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Source handling
The bundled 25-person demo uses normalized public-source records. The app validates pasted LinkedIn and Instagram URLs but does not bypass platform access controls or perform unauthorized LinkedIn scraping. For arbitrary profiles, an authorized integration or user-provided source content is required.

## Demo API
- `GET /api/people`
- `POST /api/people/import`
- `POST /api/analyze/{person_id}`
- `POST /api/date/{a_id}/{b_id}`
- `POST /api/dates/demo?limit=12`
- `POST /api/rankings/all`
- `GET /api/rankings/{person_id}`


## Final polished demo
The dataset contains 25 public-profile source pairs supplied for the demo. The UI includes animated profile cards, agent-date transitions, and ranking reveal animations. Verify public availability of each social account immediately before recording/submission.


## Dataset
The bundled `backend/people.json` contains only the 25 LinkedIn/Instagram pairs supplied by the user in the conversation. No earlier dataset entries are retained. The URLs are treated as source inputs; public-account status should be checked before submission.
