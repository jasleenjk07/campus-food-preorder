# Campus Food Pre-Ordering Platform (Cravix)

A web-based platform that reduces canteen rush during short lecture breaks by letting students pre-order food for specific pickup slots and pick it up when it is ready.

## Problem

During short breaks, students often face long queues in campus canteens, which wastes break time and leads to missed meals.

## Solution

Students browse menus, add items to a cart, choose a pickup slot, and place orders in advance. Vendors see upcoming orders grouped by slot, prepare food ahead of time, and update order status as items are ready.

## Target Users

- **Users** — browse menus, order ahead, track status, pay
- **Vendors** — manage menu, hours, orders, and preparation queue
- **Admins** — oversee users and platform activity

## Project Status

| Area | Status |
|------|--------|
| Backend API (FastAPI) | Implemented |
| Database (PostgreSQL + Alembic) | Implemented |
| Redis, WebSockets, Celery notifications | Implemented |
| Android app | External client (this repo is the API) |

## Tech Stack

| Layer | Technology |
|-------|------------|
| API | [FastAPI](https://fastapi.tiangolo.com/) (Python 3.11) |
| Database | PostgreSQL 15 |
| ORM / migrations | SQLAlchemy 2, Alembic |
| Cache / pub-sub | Redis 7 |
| Background jobs | Celery |
| Auth | JWT (python-jose), bcrypt |
| Mobile client | Android app (primary) |
| Containers | Docker Compose |

## Features

### Student (`USER`)

- Register and log in
- Browse vendors and menus
- Cart (add, update, remove items)
- Checkout with pickup slots
- Order history, tracking, and payment (simulated)
- Real-time updates via WebSocket
- In-app notifications

### Vendor (`VENDOR`)

- Vendor profile, hours, and availability
- Menu CRUD
- Dashboard (today’s orders, queue, revenue, prep time)
- Mark orders as preparing / delivered
- Low-stock alerts

### Admin (`ADMIN`)

- User management
- Platform dashboard
- Full order visibility

## Project Structure

```
campus-food-preorder/
├── backend/           # FastAPI app (Cravix API)
│   ├── app/           # routers, models, services, tasks
│   ├── alembic/       # database migrations
│   └── Dockerfile
├── frontend/          # React app (placeholder)
├── docs/
│   └── API.md         # endpoint reference
├── api.http           # HTTP client requests (VS Code REST Client)
├── docker-compose.yml
└── requirements.txt   # root-level deps (local tooling)
```

## Getting Started

### Prerequisites

- [Docker](https://www.docker.com/) and Docker Compose
- (Optional) Python 3.11+ for running the API outside Docker

### 1. Environment variables

Create `backend/.env` from the template below. Do not commit this file (it is gitignored).

```env
DATABASE_URL=postgresql+psycopg2://cravix:cravix123@localhost:5432/campus_food
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=change-me-to-a-long-random-string
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
ENVIRONMENT=development
LOG_LEVEL=DEBUG

# Optional: email notifications (Celery)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=your-email@example.com
EMAIL_PASSWORD=your-app-password
EMAIL_FROM=Cravix <your-email@example.com>
```

When using Docker Compose, `DATABASE_URL` and `REDIS_URL` are overridden in `docker-compose.yml` to point at the `postgres` and `redis` services.

### 2. Run with Docker Compose

From the repository root:

```bash
docker compose up --build
```

Services:

| Service | URL / port |
|---------|------------|
| API | http://localhost:8000 |
| PostgreSQL | `localhost:5432` |
| Redis | `localhost:6379` |

### 3. Database migrations

After Postgres is up:

```bash
cd backend
alembic upgrade head
```

Tables are also created on API startup via SQLAlchemy metadata; prefer Alembic for consistent schema in shared environments.

### 4. Verify the API

- Health: http://localhost:8000/
- Liveness: http://localhost:8000/health/live
- Readiness (DB + Redis): http://localhost:8000/health/ready
- Interactive docs: http://localhost:8000/docs

### 5. Try requests locally

Use `api.http` with the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension, or any HTTP client.

1. Register at `POST /api/v1/auth/register`
2. Log in from Android with JSON: `POST /api/v1/auth/login/json`  
   (`POST /api/v1/auth/login` remains available as OAuth2 form login for Swagger)
3. Call protected routes with `Authorization: Bearer <access_token>`

All versioned routes are under the **`/api/v1`** prefix (for example, `/api/v1/auth/login/json`, `/api/v1/orders/checkout`).

### Android notes

- Emulator base URL: `http://10.0.2.2:8000`
- Physical device: use your computer’s LAN IP, e.g. `http://192.168.x.x:8000`, and set `PUBLIC_BASE_URL` to the same value
- Cleartext HTTP requires `android:usesCleartextTraffic="true"` (or a network security config) while testing
- Keep Redis running (`docker compose up redis` or full compose); the API still works without it, but realtime push/email will be degraded

## API Documentation

- **Swagger UI:** http://localhost:8000/docs (auto-generated from FastAPI)
- **Written reference:** [docs/API.md](docs/API.md) — note that paths in that doc omit the `/api/v1` prefix; prepend it when calling the live API.

### Main route groups

| Prefix | Purpose |
|--------|---------|
| `/api/v1/auth` | Register, login, admin user creation |
| `/api/v1/users` | Current user profile |
| `/api/v1/menu` | Food items |
| `/api/v1/cart` | Shopping cart |
| `/api/v1/orders` | Checkout, payment, status, history |
| `/api/v1/pickup` | Pickup time slots |
| `/api/v1/vendor` | Vendor dashboard and profile |
| `/api/v1/notifications` | User and vendor notifications |
| `/api/v1/ws` | WebSocket real-time updates |
| `/api/v1/home` | Home / vendor listing |

## Local development (without Docker)

```bash
# Start Postgres and Redis yourself, then:
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Run Celery separately for notification emails:

```bash
celery -A app.core.celery_app worker --loglevel=info --queues=notifications
```

## Order lifecycle

```
PLACED → [pay] → PREPARING → DELIVERED
   │
   └── [cancel] → CANCELLED
```

Vendors can start preparation once payment is confirmed. Students can cancel while the order is still `PLACED`.

## License

Not specified — add a license file if you plan to open-source or distribute this project.
