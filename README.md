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
- Two-factor authentication: TOTP authenticator apps (with single-use recovery codes) and/or WebAuthn passkeys, plus an admin reset
- Session management: see every signed-in device (browser, OS, IP, last active) and sign out one or all others
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
- Dashboard, Profile, and a **Dev Console** sidebar group with four sub-modules: Users (list, create, assign roles, enable/disable), Roles, Permissions (full create/read/update/delete) and Audit Log

**Infrastructure & operations**
- Docker Compose for the whole stack, Nginx reverse proxy
- PostgreSQL with pgAdmin, Alembic migrations
- Metrics: Prometheus, Grafana, postgres-exporter, cAdvisor
- Centralized logs: Loki + Grafana Alloy, searchable in Grafana
- Alerting: Grafana alert rules for failed logins, login throttling, server errors, slow responses, a downed backend and missing backups, delivered by email
- Automated PostgreSQL backups to a Docker volume, with retention and a documented restore procedure
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
| Server errors | more than 5 HTTP 5xx responses in 5 minutes | critical |
| Slow responses | 95th percentile response time above 1 second for 5 minutes | warning |
| Backend is down | Prometheus cannot scrape the API for 2 minutes | critical |
| Database backup missing | no successful backup logged in the last 26 hours | critical |

Alerts are emailed to `ALERT_EMAIL` through Grafana's SMTP settings (Mailpit in development, so they appear at http://localhost:8025). The login rules read the backend's access logs from Loki, the reliability rules use Prometheus metrics, and the backup rule watches the backup container's logs. Change thresholds in `rules.yml` and `reliability-rules.yml` under `monitoring/grafana/provisioning/alerting/` and restart Grafana; provisioned rules are read-only in the Grafana UI.

## Database backups

The `db-backup` service writes a compressed `pg_dump` of the database to the `backups` Docker volume at startup and then every `BACKUP_INTERVAL_HOURS` (default 24), and deletes dumps older than `BACKUP_KEEP_DAYS` (default 7). `latest.dump` always points at the newest file, and each success is logged as `backup ok`, which the "Database backup missing" alert watches.

```bash
docker compose exec db-backup ls -lh /backups                      # list backups
docker compose cp db-backup:/backups/<file>.dump ./                # copy one out of the volume
```

**Check a backup** by restoring it into a scratch database:

```bash
docker compose exec db-backup sh -c 'createdb -T template0 restore_test \
  && pg_restore --no-owner --dbname=restore_test /backups/latest.dump \
  && psql -d restore_test -c "select count(*) from users"; dropdb restore_test'
```

**Restore for real** (this replaces the current data):

```bash
docker compose stop backend
docker compose exec db-backup sh -c 'pg_restore --clean --if-exists --no-owner --dbname="$PGDATABASE" /backups/<file>.dump'
docker compose start backend
```

The volume lives on the same host as the database, so also copy dumps somewhere else (another machine or object storage) on a schedule.

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
| `WEBAUTHN_RP_ID` | Passkey relying-party ID: your site's domain without scheme or port (default `localhost`). **Changing it invalidates every registered passkey** |
| `WEBAUTHN_RP_NAME` | Name shown in the browser's passkey prompt (default `RoleGate`) |
| `WEBAUTHN_ORIGINS` | Comma-separated exact browser origins allowed to use passkeys (default `http://localhost,http://localhost:5173`) |
| `FIRST_ADMIN_EMAIL`, `FIRST_ADMIN_PASSWORD` | Seeded administrator account |
| `PGADMIN_EMAIL`, `PGADMIN_PASSWORD` | pgAdmin login |
| `GRAFANA_USER`, `GRAFANA_PASSWORD` | Grafana login |
| `ALERT_EMAIL` | Recipient of Grafana alert emails (default `admin@example.com`) |
| `BACKUP_INTERVAL_HOURS`, `BACKUP_KEEP_DAYS` | Backup frequency and retention (defaults 24 and 7) |

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
| `permissions:read` / `permissions:create` / `permissions:update` / `permissions:delete` | Manage the permission catalogue (Dev Console → Permissions) |

| Default role | Permissions |
|---|---|
| `admin` | All (kept in sync automatically) |
| `manager` | `dashboard:view`, `users:read`, `roles:read` |
| `user` | `dashboard:view` (assigned on registration) |

To add a permission, append it to `PERMISSIONS` in `backend/app/seed.py`, protect an endpoint with `Depends(require_permission("your:permission"))`, and (optionally) gate UI with `auth.can('your:permission')`.

## Two-factor authentication

Any user can turn on TOTP two-factor authentication from **Profile → Two-factor authentication**: scan the QR code with an authenticator app (Google Authenticator, Authy, 1Password, ...), confirm with a 6-digit code, and save the eight one-time recovery codes that are shown once.

From then on, signing in is two steps: password, then a code from the app (or a recovery code). Codes cannot be replayed, wrong codes count towards the account lockout, and turning 2FA off requires the password plus a valid code. If someone loses both their device and their recovery codes, a user with `users:update` can click **Reset 2FA** on the Users page.

## Passkeys (WebAuthn)

Passkeys are a second factor, alongside TOTP. From **Profile → Passkeys** a user confirms their password, then registers a fingerprint, face unlock, device PIN or hardware security key. After that, signing in is two steps: password, then **Use a passkey**. If the account has both a passkey and an authenticator app, the sign-in page offers either.

- The browser only allows passkeys on `https://` or `http://localhost`, and the origin must match `WEBAUTHN_ORIGINS` and `WEBAUTHN_RP_ID`. For production set, for example, `WEBAUTHN_RP_ID=example.com` and `WEBAUTHN_ORIGINS=https://example.com`.
- Challenges are single-use, expire after 5 minutes and are stored in the database. The signature counter is checked on every sign-in, so a cloned authenticator is rejected.
- Only the public key is stored. Adding or removing a passkey needs the account password; failed passkey attempts count towards the account lockout and are audited.
- **Reset 2FA** on the Users page removes both the authenticator app and all passkeys.

## Sessions

**Profile → Signed-in devices** lists every device that is signed in to your account, with browser, OS, IP address, sign-in time and last activity, and lets you sign out a single device or all other devices.

A session is one chain of rotating refresh tokens: the session ID stays the same each time the token rotates. Signing a device out revokes its refresh token, so it cannot get a new access token. An access token that was already issued stays valid until it expires (15 minutes by default). "Last active" updates whenever the device refreshes its token, so it is accurate to roughly that interval. Revoking a device is deliberately not treated as token theft: only reuse of an already-rotated token signs out every device.

## Dev Console and permission management

The sidebar groups the administration pages under **Dev Console**: Users, Roles, Permissions and Audit Log. Each entry only appears for users who hold its `*:read` permission, and the group hides itself when none apply. Old URLs such as `/users` redirect to `/dev/users`.

The Permissions page manages the permission catalogue (`resource:action` codes, lowercase):

- Built-in permissions (the ones seeded in `backend/app/seed.py`) can have their description edited, but cannot be renamed or deleted, because the code checks them by name.
- Newly created permissions are granted to the `admin` role automatically and can be assigned to other roles on the Roles page.
- A permission only protects something once an endpoint checks it with `Depends(require_permission("your:code"))`.
- Deleting a permission removes it from every role that had it.

## Audit log

Each entry stores the actor (id and email snapshot), action, target, JSON details, client IP and timestamp. The audit row is written in the same database transaction as the change it describes.

| Action | Recorded when |
|---|---|
| `auth.register` | Someone signs up |
| `auth.login` / `auth.login_failed` | Successful / failed sign-in |
| `auth.password.change` / `auth.password.reset` | Password changed or reset |
| `auth.2fa.enable` / `auth.2fa.disable` / `auth.2fa_failed` | Two-factor set up, removed, or a wrong code or passkey entered |
| `auth.passkey.add` / `auth.passkey.remove` | A passkey is registered or removed |
| `auth.session.revoke` / `auth.session.revoke_others` | A device is signed out from the sessions page |
| `user.create` | An admin creates a user |
| `user.roles.update` | A user's roles change (before and after are stored) |
| `user.active.update` | A user is enabled or disabled |
| `user.2fa.reset` | An admin removes a user's two-factor authentication |
| `role.create` / `role.update` / `role.delete` | Role changes (with permission snapshots) |
| `permission.create` / `permission.update` / `permission.delete` | Permission catalogue changes |

To audit a new action, call `audit.record(db, request, "thing.action", actor=user, target_type=..., target_id=..., detail={...})` before committing.

## API overview

Interactive docs are at `/api/docs`.

| Area | Endpoints |
|---|---|
| Auth | `POST /api/auth/register`, `verify-email`, `resend-verification`, `login`, `refresh`, `logout`, `forgot-password`, `reset-password`, `change-password`, `login/2fa`, `2fa/setup`, `2fa/enable`, `2fa/disable`; `GET /api/auth/me` |
| Sessions | `GET /api/auth/sessions`, `POST /api/auth/sessions/{id}/revoke`, `POST /api/auth/sessions/revoke-others` |
| Passkeys | `GET /api/auth/passkeys`, `POST /api/auth/passkeys/register/options`, `register`, `{id}/remove`; sign-in: `POST /api/auth/login/webauthn/options`, `login/webauthn` |
| Users | `GET /api/users`, `POST /api/users`, `PUT /api/users/{id}/roles`, `PATCH /api/users/{id}/active`, `DELETE /api/users/{id}/2fa` |
| Roles | `GET /api/roles`, `GET /api/roles/permissions`, `POST /api/roles`, `PUT /api/roles/{id}`, `DELETE /api/roles/{id}` |
| Permissions | `GET /api/permissions`, `POST /api/permissions`, `PUT /api/permissions/{id}`, `DELETE /api/permissions/{id}` |
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
├── scripts/backup.sh            # periodic pg_dump used by the db-backup service
├── .env.example
├── nginx/default.conf
├── monitoring/
│   ├── prometheus/prometheus.yml
│   ├── loki/loki.yml
│   ├── alloy/config.alloy
│   └── grafana/provisioning/
│       ├── datasources/datasource.yml
│       └── alerting/            # rules.yml, reliability-rules.yml, contact-points.yml, policies.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt, requirements-dev.txt
│   ├── alembic.ini
│   ├── alembic/                 # migrations (env.py, versions/)
│   ├── pytest.ini, ruff.toml
│   ├── tests/                   # conftest.py, test_auth.py, test_rbac.py, test_audit.py,
│   │                            # test_rate_limit.py, test_2fa.py, test_passkeys.py, test_sessions.py, test_permissions.py
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
│       ├── webauthn_utils.py    # passkey helpers (py-webauthn wrappers)
│       ├── emailer.py
│       ├── seed.py              # default roles, permissions, admin
│       └── routers/             # auth.py, passkeys.py, sessions.py, users.py, roles.py, permissions.py, audit_logs.py
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
        ├── components/          # Sidebar, Header, Footer, UserCreateModal, TwoFactorCard, PasskeysCard, SessionsCard
        └── views/               # Login, Register, ForgotPassword, ResetPassword,
                                 # VerifyEmail, Dashboard, Users, Roles, Permissions, AuditLog, Profile
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
- TOTP secrets are encrypted at rest with a key derived from `SECRET_KEY` (rotating `SECRET_KEY` invalidates them and forces users to re-enrol), codes cannot be replayed, and recovery codes are stored only as hashes.
- Passkeys store only a public key. Challenges are single-use and short-lived, the origin and relying-party ID are verified on every assertion, and the signature counter detects cloned authenticators. Run the app behind HTTPS in production, and do not change `WEBAUTHN_RP_ID` once users have registered passkeys.

### Before going to production

- [ ] Replace every password and `SECRET_KEY` in `.env`
- [ ] Serve over HTTPS and set `COOKIE_SECURE=true`
- [ ] Deploy the published images with `docker-compose.prod.yml` (drops the `8000:8000` mapping and the migration bind mount)
- [ ] Do not expose pgAdmin, Prometheus, Grafana or Mailpit publicly (or protect them)
- [ ] Configure a real SMTP provider for the app (`SMTP_*`) and for Grafana alerts (`GF_SMTP_*`), then remove `mailpit`
- [ ] Review the Alloy Docker socket mount and Loki retention (`retention_period`)
- [ ] Copy the `backups` volume off the host on a schedule and rehearse a restore

## Roadmap

- [ ] Off-host backup copies (S3-compatible storage)

## License

MIT.