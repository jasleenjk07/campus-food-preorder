# Deploy Cravix Backend on a VPS

Recommended setup for the Android app: **Ubuntu 22.04/24.04 + Docker Compose + Nginx + HTTPS**.

## What gets installed

| Component | Role |
|-----------|------|
| `backend` | FastAPI API on `127.0.0.1:8000` |
| `postgres` | Database (internal only) |
| `redis` | Cache / WebSockets / Celery broker |
| `celery` | Email / background notifications |
| Nginx | Public HTTPS reverse proxy |
| Docker volumes | Persist DB, Redis AOF, uploads |

Files added for this:

- [`docker-compose.prod.yml`](../docker-compose.prod.yml)
- [`.env.production.example`](../.env.production.example)
- [`deploy/nginx/cravix.conf`](../deploy/nginx/cravix.conf)
- [`deploy/setup-vps.sh`](../deploy/setup-vps.sh)

---

## 1. Server prerequisites

- Ubuntu 22.04 or 24.04
- Root or sudo user
- Open firewall ports: **22**, **80**, **443**
- A domain pointing to the VPS IP (recommended), e.g. `api.yourdomain.com`

```bash
# On the VPS
sudo apt-get update
sudo apt-get install -y git curl nginx certbot python3-certbot-nginx ufw
sudo ufw allow OpenSSH
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
```

---

## 2. Clone the project

```bash
cd /opt
sudo git clone YOUR_REPO_URL campus-food-preorder
sudo chown -R $USER:$USER /opt/campus-food-preorder
cd /opt/campus-food-preorder
```

---

## 3. Create production env file

```bash
cp .env.production.example .env.production
nano .env.production
```

**Must change:**

| Variable | Example |
|----------|---------|
| `POSTGRES_PASSWORD` | strong random password |
| `SECRET_KEY` | `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `PUBLIC_BASE_URL` | `https://api.yourdomain.com` |

Leave email blank if you don’t need SMTP yet.

---

## 4. Start the stack

```bash
chmod +x deploy/setup-vps.sh
./deploy/setup-vps.sh
```

Or manually:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
docker compose -f docker-compose.prod.yml --env-file .env.production ps
curl http://127.0.0.1:8000/health/ready
```

Expected: API responds; Postgres + Redis show `connected`.

---

## 5. Nginx reverse proxy

```bash
sudo cp deploy/nginx/cravix.conf /etc/nginx/sites-available/cravix
sudo nano /etc/nginx/sites-available/cravix   # set server_name to your domain
sudo ln -sf /etc/nginx/sites-available/cravix /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

---

## 6. HTTPS (Let’s Encrypt)

```bash
sudo certbot --nginx -d api.yourdomain.com
```

Certbot will update the Nginx config for SSL.

Then confirm:

```text
https://api.yourdomain.com/
https://api.yourdomain.com/docs
https://api.yourdomain.com/health/ready
```

Update `.env.production` if needed:

```env
PUBLIC_BASE_URL=https://api.yourdomain.com
```

Restart API so image URLs use HTTPS:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d backend
```

---

## 7. Point Android at the VPS

```kotlin
const val BASE_URL = "https://api.yourdomain.com/"
```

Login:

```http
POST /api/v1/auth/login/json
Content-Type: application/json

{"email":"student@example.com","password":"password123"}
```

Use HTTPS — no cleartext traffic flag needed in production.

---

## 8. Useful commands

```bash
# Logs
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f backend
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f celery

# Restart
docker compose -f docker-compose.prod.yml --env-file .env.production restart

# Rebuild after git pull
git pull
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build

# Stop
docker compose -f docker-compose.prod.yml --env-file .env.production down
```

---

## 9. Security checklist

- [ ] Strong `POSTGRES_PASSWORD` and `SECRET_KEY` (≥ 32 chars)
- [ ] Postgres/Redis **not** published on public ports (prod compose already keeps them internal)
- [ ] API only on `127.0.0.1:8000`, public traffic via Nginx + HTTPS
- [ ] UFW enabled (22/80/443 only)
- [ ] `.env.production` never committed to git
- [ ] Create the first ADMIN yourself (self-register as ADMIN is blocked)

---

## 10. No domain yet?

You can temporarily test with the VPS IP:

1. Set Nginx `server_name` to `_` or the IP  
2. Set `PUBLIC_BASE_URL=http://YOUR_VPS_IP`  
3. In Android, allow cleartext **only for testing**, or use a free domain ASAP  

Prefer getting a free domain (or Cloudflare) + SSL before Play Store release.

---

## 11. Architecture

```text
Android app
    │ HTTPS :443
    ▼
Nginx (VPS)
    │ proxy → 127.0.0.1:8000
    ▼
Docker: backend ──► postgres
                 ──► redis ◄── celery
                 ──► uploads volume
```
