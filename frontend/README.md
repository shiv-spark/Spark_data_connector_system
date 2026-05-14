# Data Connector — Frontend

React + Vite + TypeScript + Tailwind, with TanStack Query for data fetching, react-router
for navigation, and Recharts for visuals.

## Local dev

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000  →  proxies /api → backend on :8000
```

Set `VITE_API_BASE_URL` in `frontend/.env` if your backend isn't at `http://localhost:8000`.

## Production build

```bash
npm run build        # outputs to dist/
npm run preview      # serve the build locally
```

## Docker

The root `Dockerfile.frontend` builds the app and serves it via nginx on port 80
(mapped to `:3000` on the host by `docker-compose.yml`).

```bash
docker compose up -d frontend
# open http://localhost:3000
```

## Layout

```
frontend/
├── index.html
├── package.json
├── vite.config.ts            # dev proxy to the FastAPI backend
├── tailwind.config.ts
└── src/
    ├── main.tsx              # router + react-query bootstrap
    ├── App.tsx               # routes
    ├── index.css             # tailwind + design tokens
    ├── lib/
    │   ├── api.ts            # axios instance
    │   ├── cn.ts             # tailwind class merger
    │   └── format.ts         # date / number helpers
    ├── components/
    │   ├── Layout.tsx        # sidebar + health indicator
    │   ├── Kpi.tsx
    │   └── StatusBadge.tsx
    └── pages/
        ├── Dashboard.tsx     # ✅ wired to /dashboard/summary
        ├── Pipelines.tsx     # ✅ wired to /pipelines + status/pause/resume/delete
        ├── CreatePipeline.tsx
        ├── DirectIngest.tsx
        ├── DataPreview.tsx
        ├── Metrics.tsx
        ├── Logs.tsx
        ├── MultiSource.tsx
        └── Assistant.tsx
```

Pages marked ✅ are functional. The rest are placeholders ready to flesh out.