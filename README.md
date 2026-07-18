# Nova Support Agent

A customer-facing AI support agent built with FastAPI + Claude. It answers
questions using a FAQ knowledge base and a (mock) CRM, and escalates to a
human when it can't resolve something — logged to a simple dashboard.

## What's inside

- `app.py` — FastAPI server: chat page, chat API, dashboard, escalation resolve endpoint
- `agent.py` — Claude tool-use loop (the actual "agent" logic)
- `escalations.py` — SQLite-backed escalation log
- `data/customers.json` — mock CRM (3 sample customers) — replace with a real CRM API later
- `data/faqs.json` — FAQ knowledge base — edit this with your real FAQs
- `templates/chat.html` — the live chat widget customers use
- `templates/dashboard.html` — internal view of escalated cases

## 1. Run it locally first

```bash
cd support-agent
pip install -r requirements.txt
export ANTHROPIC_API_KEY=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 # get this from console.anthropic.com
uvicorn app:app --reload --port 8000
```

Open:
- `http://localhost:8000` — the chat widget
- `http://localhost:8000/dashboard` — escalated cases

Try these to see the different behaviors:
- "How do I reset my password?" → answered straight from FAQ
- "I'm james.whitfield@example.com, why is my dashboard slow?" → looks up the customer, sees their open ticket, gives a context-aware answer
- "I want a refund and this is ridiculous" → escalates, shows up on `/dashboard`

## 2. Customize it for your business

- Replace the contents of `data/faqs.json` with your real FAQs.
- Replace `data/customers.json` (and the `lookup_customer` function in
  `agent.py`) with a real CRM API call once you're ready — HubSpot, Salesforce,
  and Zendesk all have simple REST APIs for looking up a contact by email.
- Edit `SYSTEM_PROMPT` in `agent.py` to match your company's name, tone, and
  escalation rules.

## 3. Deploy it live (Render — free tier)

1. Push this folder to a new GitHub repo (public or private both work).
2. Go to https://render.com → sign up/log in with GitHub.
3. Click **New > Web Service**, select your repo. Render will detect
   `render.yaml` automatically and pre-fill the build/start commands.
4. Under **Environment**, add:
   - `ANTHROPIC_API_KEY` = your key from console.anthropic.com
5. Click **Create Web Service**. First deploy takes ~2-3 minutes.
6. You'll get a live URL like `https://nova-support-agent.onrender.com` —
   that's your shareable, clickable link.

Notes on the free tier: the service spins down after 15 minutes of
inactivity and takes ~30-60 seconds to wake back up on the next request —
fine for testing/demoing, worth upgrading to a paid instance ($7/mo) before
sending it to real customers.

## 4. Known limitations of this MVP (by design, for a fast first version)

- Escalations log to a local SQLite file — fine for one Render instance,
  but will need Postgres if you scale to multiple instances.
- Chat sessions are stored in memory — restarting the server clears active
  conversations (finished conversations are unaffected since escalations
  are already saved to the DB).
- CRM is mock data — 3 fake customers to prove the pattern works.

None of these block a live demo; they're the natural next upgrades once
you're validating this with real customers.
