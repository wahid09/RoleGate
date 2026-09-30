# RoleGate

![CI](https://github.com/wahid09/RoleGate/actions/workflows/ci.yml/badge.svg)

**Authentication & role-based access control (RBAC) admin platform.**

RoleGate is a full-stack starter for apps that need secure sign-up, sign-in and fine-grained permissions. Users register, verify their email and land on a professional admin dashboard (sidebar, header, footer, content area) where menus and actions adapt to their permissions. It is built with **FastAPI**, **Vue 3** and **Bootstrap 5**, and ships as a single `docker compose` stack with Nginx, PostgreSQL, Redis, and a Prometheus + Grafana + Loki observability setup. Every sensitive action is recorded in an audit log, and the project comes with automated tests and a GitHub Actions pipeline.

---

## Features

**Authentication**
- Registration with email verification
- Login with short-lived JWT access tokens (15 min) and rotating refresh tokens in httpOnly cookies, with reuse detection
- Forgot / reset password by email
- Change password from the profile page (other devices are signed out)
- Redis rate limiting on sensitive endpoints, plus per-account lockout after repeated failed logins

**Authorization (RBAC)**
- Users, roles and permissions (`resource:action`, e.g. `users:read`)
- Default roles: `admin`, `manager`, `user`
- Create custom roles and assign permissions from the UI
- Permissions enforced in the API (`require_permission`) and reflected in the UI (menus, buttons, route guards)

**Audit log**
- Who did what, when and from which IP, stored in PostgreSQL
- Records sign-ins (including failures), registrations, password changes, user creation, role assignments, enable/disable, and role create/update/delete, with before/after details
- Searchable, paginated Audit Log page (requires the `audit:read` permission)

**Admin dashboard**
- Responsive Bootstrap 5 layout with collapsible sidebar, header user menu and footer
- Dashboard, Users (list, create, assign roles, enable/disable), Roles & Permissions, Audit Log, Profile

**Infrastructure & operations**
- Docker Compose for the whole stack, Nginx reverse proxy
- PostgreSQL with pgAdmin, Alembic migrations
- Metrics: Prometheus, Grafana, postgres-exporter, cAdvisor
- Centralized logs: Loki + Grafana Alloy, searchable in Grafana
- Alerting: Grafana alert rules for failed-login spikes and login throttling, delivered by email
- Releases: tagged versions publish Docker images to GitHub Container Registry
- Mailpit to catch emails in development

**Quality**
- Backend tests (pytest) against real PostgreSQL and Redis, including rate-limit tests; frontend tests (Vitest)
- GitHub Actions: lint, migration checks, tests, production build and Docker image build

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, PyJWT, bcrypt |
| Frontend | Vue 3, Vite, Pinia, Vue Router, Axios, Bootstrap 5, Bootstrap Icons |
| Data | PostgreSQL 16, Redis 7 |
| Proxy | Nginx |
| Observability | Prometheus, Grafana, Loki, Grafana Alloy, postgres-exporter, cAdvisor |
| Testing & CI | pytest, Vitest, Ruff, GitHub Actions |
| Dev tools | Docker Compose, pgAdmin, Mailpit |

## Architecture

```mermaid
flowchart LR
    Browser --> Nginx
    Nginx -->|/| Frontend[Vue SPA]
    Nginx -->|/api| Backend[FastAPI]
    Backend --> Postgres[(PostgreSQL)]
    Backend --> Redis[(Redis)]
    Backend --> Mailpit
    pgAdmin --> Postgres

    Prometheus --> Backend
    Prometheus --> PGExporter[postgres-exporter] --> Postgres
    Prometheus --> cAdvisor
    Alloy["Grafana Alloy"] -. container logs .-> Loki
    Grafana --> Prometheus
    Grafana --> Loki
```

## Quick start

**Requirements:** Docker and Docker Compose v2.

```bash
git clone https://github.com/wahid09/RoleGate.git
cd RoleGate

cp .env.example .env        # then edit .env and change every password / secret
docker compose up -d --build
```

Database migrations are applied automatically when the backend starts, and the default roles, permissions and first admin account are seeded.

| Service | URL | Notes |
|---|---|---|
| App | http://localhost | Sign in with `FIRST_ADMIN_EMAIL` / `FIRST_ADMIN_PASSWORD` from `.env` |
| API docs (Swagger) | http://localhost/api/docs | |
| Mailpit (caught emails) | http://localhost:8025 | Verification and reset links appear here |
| pgAdmin | http://localhost:5050 | Server host `db`, port `5432` |
| Grafana | http://localhost:3000 | Prometheus and Loki data sources are pre-provisioned |
| Prometheus | http://localhost:9090 | |

## Monitoring and logs

**Metrics.** In Grafana, go to *Dashboards → Import* and use ID `9628` (PostgreSQL) and `14282` (cAdvisor containers). API request metrics (`http_requests_total`, latency histograms) are scraped from the backend's `/metrics` endpoint, which is only reachable inside the Docker network.

**Logs.** Grafana Alloy tails every container's output through the Docker socket and ships it to Loki (7-day retention, configurable in `monitoring/loki/loki.yml`). In Grafana open *Explore*, choose the **Loki** data source and try:

```logql
{service="backend"}                               # all API logs
{service="backend"} |= "POST /api/auth/login"     # login traffic
{service="nginx"} |= " 502 "                      # gateway errors
{platform="docker"} |= "ERROR"                    # errors from any container
```

Promtail is not used because it reached end of life in March 2026; Alloy is its successor.

## Alerting

Grafana alert rules, a contact point and a notification policy are provisioned from `monitoring/grafana/provisioning/alerting/`, so they are version controlled and appear automatically after `docker compose up`.

| Rule | Fires when | Severity |
|---|---|---|
| Failed login spike | more than 10 failed logins (HTTP 401) in 5 minutes | warning |
| Login throttling triggered | more than 5 login requests rejected with HTTP 429 (rate limit or account lockout) in 5 minutes | critical |

Alerts are emailed to `ALERT_EMAIL` through Grafana's SMTP settings (Mailpit in development, so they appear at http://localhost:8025). The rules read the backend's access logs from Loki. Change thresholds in `monitoring/grafana/provisioning/alerting/rules.yml` and restart Grafana; provisioned rules are read-only in the Grafana UI.

## Configuration

All settings live in `.env` (see `.env.example`).

| Variable | Description |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Database credentials |
| `DATABASE_URL` | SQLAlchemy URL used by the backend |
| `SECRET_KEY` | JWT signing key: use a long random value |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime (default 15) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime (default 7) |
| `RESET_TOKEN_EXPIRE_MINUTES` | Password reset link lifetime (default 30) |
| `VERIFY_TOKEN_EXPIRE_HOURS` | Email verification link lifetime (default 24) |
| `COOKIE_SECURE` | Set `true` when served over HTTPS |
| `FRONTEND_URL` | Base URL used in email links |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Outgoing email (Mailpit by default) |
| `REDIS_URL` | Redis connection for rate limiting |
| `RATE_LIMIT_ENABLED` | Set `false` to disable rate limiting and lockout (default `true`; the test suite turns it off) |
| `LOGIN_MAX_FAILURES`, `LOGIN_LOCK_SECONDS` | Account lockout policy |
| `FIRST_ADMIN_EMAIL`, `FIRST_ADMIN_PASSWORD` | Seeded administrator account |
| `PGADMIN_EMAIL`, `PGADMIN_PASSWORD` | pgAdmin login |
| `GRAFANA_USER`, `GRAFANA_PASSWORD` | Grafana login |
| `ALERT_EMAIL` | Recipient of Grafana alert emails (default `admin@example.com`) |

## Roles and permissions

| Permission | Allows |
|---|---|
| `dashboard:view` | Open the dashboard |
| `users:read` | List users |
| `users:create` | Create users |
| `users:update` | Change user roles, enable/disable users |
| `roles:read` | List roles and permissions |
| `roles:create` / `roles:update` / `roles:delete` | Manage roles |
| `audit:read` | View the audit log |

| Default role | Permissions |
|---|---|
| `admin` | All (kept in sync automatically) |
| `manager` | `dashboard:view`, `users:read`, `roles:read` |
| `user` | `dashboard:view` (assigned on registration) |

To add a permission, append it to `PERMISSIONS` in `backend/app/seed.py`, protect an endpoint with `Depends(require_permission("your:permission"))`, and (optionally) gate UI with `auth.can('your:permission')`.

## Audit log

Each entry stores the actor (id and email snapshot), action, target, JSON details, client IP and timestamp. The audit row is written in the same database transaction as the change it describes.

| Action | Recorded when |
|---|---|
| `auth.register` | Someone signs up |
| `auth.login` / `auth.login_failed` | Successful / failed sign-in |
| `auth.password.change` / `auth.password.reset` | Password changed or reset |
| `user.create` | An admin creates a user |
| `user.roles.update` | A user's roles change (before and after are stored) |
| `user.active.update` | A user is enabled or disabled |
| `role.create` / `role.update` / `role.delete` | Role changes (with permission snapshots) |

To audit a new action, call `audit.record(db, request, "thing.action", actor=user, target_type=..., target_id=..., detail={...})` before committing.

## API overview

Interactive docs are at `/api/docs`.

| Area | Endpoints |
|---|---|
| Auth | `POST /api/auth/register`, `verify-email`, `resend-verification`, `login`, `refresh`, `logout`, `forgot-password`, `reset-password`, `change-password`; `GET /api/auth/me` |
| Users | `GET /api/users`, `POST /api/users`, `PUT /api/users/{id}/roles`, `PATCH /api/users/{id}/active` |
| Roles | `GET /api/roles`, `GET /api/roles/permissions`, `POST /api/roles`, `PUT /api/roles/{id}`, `DELETE /api/roles/{id}` |
| Audit | `GET /api/audit-logs` (query: `page`, `page_size`, `action` prefix, `actor` email substring) |
| System | `GET /api/health` |

## Project structure

```
RoleGate/
├── .github/workflows/
│   ├── ci.yml                   # lint, tests, build
│   └── publish.yml              # release: push images to GHCR
├── docker-compose.yml
├── docker-compose.prod.yml      # run published images instead of building
├── .env.example
├── nginx/default.conf
├── monitoring/
│   ├── prometheus/prometheus.yml
│   ├── loki/loki.yml
│   ├── alloy/config.alloy
│   └── grafana/provisioning/
│       ├── datasources/datasource.yml
│       └── alerting/            # rules.yml, contact-points.yml, policies.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt, requirements-dev.txt
│   ├── alembic.ini
│   ├── alembic/                 # migrations (env.py, versions/)
│   ├── pytest.ini, ruff.toml
│   ├── tests/                   # conftest.py, test_auth.py, test_rbac.py, test_audit.py,
│   │                            # test_rate_limit.py
│   └── app/
│       ├── main.py              # app, lifespan, metrics
│       ├── config.py            # settings from environment
│       ├── database.py
│       ├── models.py            # User, Role, Permission, tokens, AuditLog
│       ├── schemas.py
│       ├── security.py          # password hashing, JWT, token hashing
│       ├── deps.py              # current user, require_permission
│       ├── ratelimit.py         # Redis rate limiting + lockout
│       ├── audit.py             # audit.record() helper
│       ├── emailer.py
│       ├── seed.py              # default roles, permissions, admin
│       └── routers/             # auth.py, users.py, roles.py, audit_logs.py
└── frontend/
    ├── Dockerfile
    ├── nginx.conf
    ├── package.json, package-lock.json
    ├── vite.config.js
    └── src/
        ├── main.js, App.vue, style.css
        ├── api/http.js          # Axios + silent token refresh (+ http.test.js)
        ├── stores/auth.js       # Pinia auth store (+ auth.test.js)
        ├── router/index.js      # route guards
        ├── layouts/AdminLayout.vue
        ├── components/          # Sidebar, Header, Footer, UserCreateModal
        └── views/               # Login, Register, ForgotPassword, ResetPassword,
                                 # VerifyEmail, Dashboard, Users, Roles, AuditLog, Profile
```

## Development

**Frontend with hot reload**

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, proxies /api to localhost:8000
```

**Database migrations (Alembic)**

```bash
# after editing backend/app/models.py
docker compose run --rm backend alembic revision --autogenerate -m "describe change"
docker compose up -d --build backend     # applies `alembic upgrade head` on startup

docker compose run --rm backend alembic current      # show applied revision
docker compose run --rm backend alembic downgrade -1 # roll back one step
```

Always review generated migrations before committing them, and commit the files in `backend/alembic/versions/`.

**Logs**

```bash
docker compose logs -f backend
```

## Testing

**Backend** (pytest, real PostgreSQL). The suite drops and recreates tables, so use a throwaway database. It refuses to run unless the database name ends with `test`.

```bash
docker run -d --name pg-test -e POSTGRES_USER=test -e POSTGRES_PASSWORD=test \
  -e POSTGRES_DB=test -p 55432:5432 postgres:16-alpine

cd backend
python -m venv .venv
source .venv/bin/activate            # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

export DATABASE_URL=postgresql+psycopg2://test:test@127.0.0.1:55432/test
                                     # PowerShell: $env:DATABASE_URL = "postgresql+psycopg2://test:test@127.0.0.1:55432/test"
pytest -q
ruff check .
```

Emails are captured in memory and rate limiting is switched off during tests, except in `test_rate_limit.py`. Those tests need a Redis server and are skipped when none is reachable:

```bash
docker run -d --name redis-test -p 56379:6379 redis:7-alpine
export REDIS_URL=redis://127.0.0.1:56379/0
                                     # PowerShell: $env:REDIS_URL = "redis://127.0.0.1:56379/0"
pytest -q
```

**Frontend** (Vitest)

```bash
cd frontend
npm ci
npm test
npm run build
```

## Continuous integration

`.github/workflows/ci.yml` runs on every push to `main` and on pull requests:

| Job | Steps |
|---|---|
| `backend` | Ruff lint, `alembic upgrade head` on an empty database, `alembic check` (models and migrations in sync), pytest against PostgreSQL and Redis services (including the rate-limit tests) |
| `frontend` | `npm ci`, Vitest, production build |
| `docker` | Validates `docker-compose.yml` and builds the backend and frontend images |

If `alembic check` fails, you changed `models.py` without generating a migration.

## Releases and container images

Pushing a version tag runs the full CI pipeline and, if it passes, publishes both images to GitHub Container Registry:

```bash
git tag v1.0.0
git push origin v1.0.0
```

| Image | Tags |
|---|---|
| `ghcr.io/wahid09/rolegate-backend` | `1.0.0`, `1.0`, `latest`, `sha-<commit>` |
| `ghcr.io/wahid09/rolegate-frontend` | same |

The workflow can also be started manually from the Actions tab (it then publishes `main` and `sha-<commit>` tags).

To run the published images instead of building locally:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

`docker-compose.prod.yml` swaps `build:` for `image:` and removes the development-only port mapping and migration bind mount (needs Docker Compose 2.24.4 or newer). Set `ROLEGATE_VERSION=1.0.0` to pin a version. New packages are private by default: make them public in the package settings, or run `docker login ghcr.io` with a token that has `read:packages` on the server.

## Security notes

- Passwords are hashed with bcrypt; refresh, reset and verification tokens are stored only as SHA-256 hashes.
- Refresh tokens live in httpOnly, `SameSite=Lax` cookies scoped to `/api/auth`, rotate on every use, and reuse of an old token revokes all of that user's sessions.
- Rate limiting reads the client IP from the `X-Real-IP` header set by Nginx, so keep Nginx as the only public entry point.
- Grafana Alloy mounts the Docker socket (read-only) to discover containers. Read-only still grants broad access to the Docker API, so on shared production hosts prefer a Docker log driver or a socket proxy.
- The audit log is append-only from the application's point of view; there is no API to edit or delete entries.

### Before going to production

- [ ] Replace every password and `SECRET_KEY` in `.env`
- [ ] Serve over HTTPS and set `COOKIE_SECURE=true`
- [ ] Deploy the published images with `docker-compose.prod.yml` (drops the `8000:8000` mapping and the migration bind mount)
- [ ] Do not expose pgAdmin, Prometheus, Grafana or Mailpit publicly (or protect them)
- [ ] Configure a real SMTP provider for the app (`SMTP_*`) and for Grafana alerts (`GF_SMTP_*`), then remove `mailpit`
- [ ] Review the Alloy Docker socket mount and Loki retention (`retention_period`)
- [ ] Set up database backups

## Roadmap

- [ ] Two-factor authentication
- [ ] Automated database backups
- [ ] Alert rules for server errors and latency

## License

MIT.
