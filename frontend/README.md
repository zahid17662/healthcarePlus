# MediBook — Frontend

React 18 + TypeScript (strict) + Tailwind CSS SPA for the hospital appointment-booking PRD.

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # type-check + production build
```

## Backend connection

`VITE_API_URL` (see `.env.example`) selects the data source:

| `VITE_API_URL` | Behaviour |
|---|---|
| `http://localhost:8000` | Real FastAPI backend in [`../backend`](../backend/README.md) (PostgreSQL). Start it first. |
| *(empty)* | In-browser **mock API** (`src/api/mockApi.ts`, localStorage) — no server needed. |

Restart `npm run dev` after changing `.env` (Vite reads it at startup).

`src/api/http.ts` is the only file that knows the wire format: it prefixes `/api/v1`, sends
`Authorization: Bearer <jwt>`, reads FastAPI's `{ "detail": "…" }` errors, and converts the API's
UPPERCASE enums (`CONFIRMED`, `ADMIN`) to the lowercase values used by the UI. The full endpoint list
is in the backend README.

### Mock mode demo accounts

Defined in `src/data/seed.ts` (the login page has "fill" buttons). They exist **only** in the mock,
never on a real backend.

| Role    | Email                   | Password      |
|---------|-------------------------|---------------|
| Admin   | admin@medibook.test     | Admin@123     |
| Patient | patient@medibook.test   | Patient@123   |

Reset mock data by clearing the site's localStorage (`medibook.mockdb.v1`). With the real backend,
register a patient in the UI; the admin account comes from `backend/scripts/seed.py`.

## Behaviour worth knowing

- A booked slot is disabled in the grid; if another patient takes it first, the server answers **409**,
  the selection is cleared and the grid refreshes (it also re-polls every 20 s).
- When the chosen doctor has no open slots, the recommendation panel lists same-specialty alternatives.

## Structure

```
src/
  api/         HealthcareApi contract, HTTP client, mock backend
  components/  ui primitives, layout (sidebar/header), booking, doctors
  context/     auth, theme (light/dark), toasts
  lib/         date + slot logic, hooks, errors
  pages/       patient pages + admin/*
  routes/      role-protected routes
  types/       domain models (PRD §6)
```
