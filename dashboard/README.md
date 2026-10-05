# Sora Semantic Dashboard

Next.js dashboard that renders read-only dashboard JSON served by FastAPI. All analytics queries go through `/api/v1/query`; the browser never reads Silver directly.

## Local development

1. Install Node.js 20.12+ and pnpm 10+.
2. Copy `.env.example` to `.env` and set `NEXT_PUBLIC_API_BASE_URL` to the FastAPI origin. Root `.env` values are shared; `dashboard/.env` overrides matching values.
3. Allow the Dashboard origin in the API's `DASHBOARD_CORS_ORIGINS` (default local origin is `http://localhost:3000`).
4. Run `pnpm install` and `pnpm dev` from this directory.

Build and validation: `pnpm typecheck`, `pnpm test`, then `pnpm build`.

Dashboard definitions are served by `GET /api/v1/dashboards` and `GET /api/v1/dashboards/{id}` from `backend/dashboard/config/`.
