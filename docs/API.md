# Campus Food Pre-Order API Documentation

Base URL: `/` (e.g., `http://localhost:8000`)

## Authentication

Most endpoints require a Bearer token. Include it in the request header:

```
Authorization: Bearer <access_token>
```

---

## Health Check

### GET /

Simple health check to verify the backend is running.

**Auth:** None

**Response:**
```json
{
  "message": "Backend is running"
}
```

---

## Auth (`/auth`)

### POST /auth/register

Register a new user (self-registration). New users get the `USER` role by default.

**Auth:** None

**Request body:**
```json
{
  "name": "string",
  "email": "user@example.com",
  "password": "string",
  "university_id": 1
}
```

| Field          | Type   | Required | Description                  |
|----------------|--------|----------|------------------------------|
| name           | string | Yes      | User's display name          |
| email          | string | Yes      | Valid email (must be unique) |
| password       | string | Yes      | User's password              |
| university_id  | int    | No       | Associated university ID     |

**Response:** `UserResponse` (200)
```json
{
  "id": 1,
  "name": "string",
  "email": "user@example.com",
  "role": "USER"
}
```

**Errors:**
- `400` — Email already registered

---

### POST /auth/create-user

Create a new user (admin only). Admin can assign any role (`USER`, `VENDOR`, `ADMIN`).

**Auth:** Bearer token (ADMIN)

**Request body:**
```json
{
  "name": "string",
  "email": "user@example.com",
  "password": "string",
  "university_id": 1,
  "role": "USER"
}
```

**Response:** `UserResponse` (200)

---

### POST /auth/login

Authenticate and receive a JWT access token.

**Auth:** None (use OAuth2 form data)

**Request body:** `application/x-www-form-urlencoded`
| Field    | Type   | Description              |
|----------|--------|--------------------------|
| username | string | User's email             |
| password | string | User's password          |

**Response:** `LoginResponse` (200)
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "name": "string",
    "email": "user@example.com",
    "role": "USER"
  }
}
```

**Errors:**
- `401` — Invalid credentials

---

## Users (`/users`)

### GET /users/me

Get the current user's profile.

**Auth:** Bearer token (any authenticated user)

**Response:** `UserResponse` (200)
```json
{
  "id": 1,
  "name": "string",
  "email": "user@example.com",
  "role": "USER"
}
```

---

## Admin (`/admin`)

### GET /admin/users

List all users. Admin only.

**Auth:** Bearer token (ADMIN)

**Response:** Array of `User` objects (200)

---

### GET /admin/dashboard

Admin dashboard placeholder.

**Auth:** Bearer token (ADMIN)

**Response:**
```json
{
  "message": "Welcome Admin"
}
```

---

### POST /admin/menu

Placeholder to add menu item. Vendor only (despite path).

**Auth:** Bearer token (VENDOR)

**Response:**
```json
{
  "message": "Food item added"
}
```

---

### POST /admin/orders

Placeholder to place order. User only (despite path).

**Auth:** Bearer token (USER)

**Response:**
```json
{
  "message": "Order placed"
}
```

---

## Menu (`/menu`)

### POST /menu

Add a new food item to the menu. Food is linked to the logged-in vendor/admin.

**Auth:** Bearer token (ADMIN or VENDOR)

**Request body:**
```json
{
  "name": "string",
  "description": "string",
  "price": 12.99
}
```

| Field       | Type   | Required | Description          |
|-------------|--------|----------|----------------------|
| name        | string | Yes      | Food item name       |
| description | string | No       | Food description     |
| price       | float  | Yes      | Price per unit       |

**Response:** `FoodResponse` (200)
```json
{
  "id": 1,
  "name": "string",
  "description": "string",
  "price": 12.99,
  "is_available": true
}
```

---

### GET /menu

List all available food items. Only returns items where `is_available == true`.

**Auth:** None

**Response:** Array of `FoodResponse` (200)
```json
[
  {
    "id": 1,
    "name": "string",
    "description": "string",
    "price": 12.99,
    "is_available": true
  }
]
```

---

## Orders (`/orders`)

### POST /orders

Place a new order.

**Auth:** Bearer token (USER)

**Request body:**
```json
{
  "food_id": 1,
  "quantity": 2
}
```

| Field    | Type | Required | Description       |
|----------|------|----------|-------------------|
| food_id  | int  | Yes      | ID of the food    |
| quantity | int  | No       | Default: 1        |

**Response:** `OrderResponse` (200)
```json
{
  "id": 1,
  "food_id": 1,
  "quantity": 2,
  "total_price": 25.98,
  "status": "PLACED",
  "is_paid": false,
  "payment_method": null,
  "created_at": "2025-02-10T12:00:00"
}
```

**Errors:**
- `404` — Food item not found or not available

---

### GET /orders/me

Get orders for the current user.

**Auth:** Bearer token (USER)

**Response:** Array of `OrderResponse` (200)

---

### GET /orders/vendor

Get orders for food items sold by the current vendor.

**Auth:** Bearer token (VENDOR)

**Response:** Array of `OrderResponse` (200)

---

### GET /orders/admin

Get all orders (admin only).

**Auth:** Bearer token (ADMIN)

**Response:** Array of `OrderResponse` (200)

---

### GET /orders/ping

Simple health check for the orders module.

**Auth:** None

**Response:**
```json
{
  "status": "orders alive"
}
```

---

### POST /orders/{order_id}/pay

Pay for an order. Simulates payment (80% success, 20% failure for immediate methods).

**Auth:** Bearer token (USER)

**Path params:** `order_id` (int)

**Query params:** `payment_method` (optional)
- `UPI_INAPP` (default)
- `CARD`
- `WALLET`
- `COD` — Cash on delivery (paid after delivery)
- `PAY_LATER` — Pay after delivery

**Response:** `OrderResponse` (200)

**Errors:**
- `404` — Order not found
- `400` — Order already paid
- `400` — Payment not allowed (order not in PLACED)
- `400` — Payment failed (simulated)

---

### PUT /orders/{order_id}/prepare

Mark an order as being prepared (VENDOR only). Order must be paid first.

**Auth:** Bearer token (VENDOR)

**Path params:** `order_id` (int)

**Response:** `OrderResponse` (200)

**Errors:**
- `404` — Order not found
- `400` — Order must be paid before preparation

---

### PUT /orders/{order_id}/deliver

Mark an order as delivered. For `PAY_LATER`, sets `is_paid` to true automatically.

**Auth:** Bearer token (ADMIN)

**Path params:** `order_id` (int)

**Response:** `OrderResponse` (200)

**Errors:**
- `404` — Order not found

---

### PUT /orders/{order_id}/cancel

Cancel an order.

**Auth:** Bearer token (USER or ADMIN)

- **USER:** Can cancel only their own order and only if status is `PLACED`
- **ADMIN:** Can cancel any order at any time

**Path params:** `order_id` (int)

**Response:** `OrderResponse` (200)

**Errors:**
- `404` — Order not found
- `403` — Not your order (USER)
- `400` — Order cannot be cancelled after preparation (USER)

---

## Order Status Flow

```
PLACED → [pay] → PAID → [prepare] → PREPARING → [deliver] → DELIVERED
   │
   └── [cancel] → CANCELLED
```

---

## Data Models

### UserResponse
| Field | Type   |
|-------|--------|
| id    | int    |
| name  | string |
| email | string |
| role  | string |

### FoodResponse
| Field         | Type   |
|---------------|--------|
| id            | int    |
| name          | string |
| description   | string |
| price         | float  |
| is_available  | bool   |

### OrderResponse
| Field          | Type   |
|----------------|--------|
| id             | int    |
| food_id        | int    |
| quantity       | int    |
| total_price    | float  |
| status         | string |
| is_paid        | bool   |
| payment_method | string |
| created_at     | datetime |
