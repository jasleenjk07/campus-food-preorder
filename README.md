# Campus Food Pre-Ordering Platform (Cravix)

API backend for the Cravix Android app. Students pre-order campus canteen food for lecture-break pickup slots; vendors prepare orders ahead of time.

## Target Users

- **Students** — browse menus, order ahead, track status, pay
- **Vendors** — manage menu, hours, orders, and preparation queue
- **Admins** — oversee users and platform activity

## Tech Stack

| Layer | Technology |
|-------|------------|
| API | FastAPI (Python 3.11) |
| Database | PostgreSQL 15 |
| ORM / migrations | SQLAlchemy 2, Alembic |
| Cache / pub-sub | Redis 7 |
| Background jobs | Celery |
| Mobile client | Android |
| Deploy | Docker Compose on a VPS + Nginx |

## Project Structure

```
campus-food-preorder/
├── backend/                 # FastAPI app
│   ├── app/
│   ├── alembic/
│   ├── Dockerfile
│   └── requirements.txt
├── deploy/
│   ├── nginx/cravix.conf    # reverse proxy + WebSockets
│   └── setup-vps.sh
├── docs/
│   ├── API.md
│   └── VPS.md               # production deploy guide
├── docker-compose.yml       # local development
├── docker-compose.prod.yml  # VPS production
├── .env.production.example
└── api.http
```

## Deploy on VPS (production)

Full guide: **[docs/VPS.md](docs/VPS.md)**

```bash
cp .env.production.example .env.production
nano .env.production          # set POSTGRES_PASSWORD, SECRET_KEY, PUBLIC_BASE_URL
chmod +x deploy/setup-vps.sh
./deploy/setup-vps.sh
# then Nginx + Certbot — see docs/VPS.md
```

Android base URL after SSL:

```text
https://api.yourdomain.com/
```

## Local development

### Prerequisites

- Docker and Docker Compose

### 1. Environment

```bash
cp backend/.env.example backend/.env
# edit SECRET_KEY and optional email settings
```

### 2. Start stack

```bash
docker compose up --build
```

| Service | URL / port |
|---------|------------|
| API | http://localhost:8000 |
| Swagger | http://localhost:8000/docs |
| Health | http://localhost:8000/health/ready |

### 3. Auth (Android / JSON)

```http
POST /api/v1/auth/register
POST /api/v1/auth/login/json
```

Send `Authorization: Bearer <access_token>` on protected routes.

All versioned routes use the **`/api/v1`** prefix.

### Android local testing

- Emulator: `http://10.0.2.2:8000`
- Physical device: `http://YOUR_LAN_IP:8000` (set `PUBLIC_BASE_URL` to match)

## Main API groups

| Prefix | Purpose |
|--------|---------|
| `/api/v1/auth` | Register, login, admin user creation |
| `/api/v1/users` | Current user profile |
| `/api/v1/menu` | Food items |
| `/api/v1/cart` | Shopping cart |
| `/api/v1/orders` | Checkout, payment, status, history |
| `/api/v1/pickup` | Pickup time slots |
| `/api/v1/vendor` | Vendor dashboard and profile |
| `/api/v1/notifications` | Notifications |
| `/api/v1/ws` | WebSocket updates |
| `/api/v1/home` | Vendor listing |

More detail: [docs/API.md](docs/API.md) (prepend `/api/v1` to paths in that doc).

## Order lifecycle

```
PLACED → [pay] → PAID → PREPARING → DELIVERED
   │
   └── [cancel] → CANCELLED
```
