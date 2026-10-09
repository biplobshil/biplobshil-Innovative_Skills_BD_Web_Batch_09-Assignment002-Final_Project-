# GatherHub

**GatherHub** is an event booking system: a REST API for publishing events and booking
tickets, built with **Django REST Framework**.

- JWT authentication (register, login, refresh, logout)
- Three roles: **admin**, **organizer**, **user**
- Category and event CRUD with search, filtering, ordering and pagination
- Event image upload
- Ticket booking with safe seat accounting and a ticket limit per booking
- QR code tickets, single-use check-in and an attendance report

| | |
|---|---|
| Live frontend | <https://gatherhub.biplobshil.online/> |
| Live API | <https://biplobshil-innovativeskillsbdwebbatch09-ass-production.up.railway.app> |
| API docs (Swagger) | <https://biplobshil-innovativeskillsbdwebbatch09-ass-production.up.railway.app/api/docs/> |
| Health check | <https://biplobshil-innovativeskillsbdwebbatch09-ass-production.up.railway.app/api/health/> |
| Admin panel | <https://biplobshil-innovativeskillsbdwebbatch09-ass-production.up.railway.app/admin/> |

The frontend is a separate web app that consumes this API.

## Contents

1. [Project setup](#project-setup)
2. [Environment variables](#environment-variables)
3. [Authentication flow](#authentication-flow)
4. [API endpoints](#api-endpoints)
5. [Testing the API with Swagger](#testing-the-api-with-swagger)
6. [Deployment](#deployment)

## Project setup

Requires Python 3.12 or newer.

```bash
# 1. Clone
git clone <your-repo-url>
cd <repo-folder>

# 2. Virtual environment
python -m venv .venv
.venv\Scripts\activate           # macOS / Linux: source .venv/bin/activate

# 3. Dependencies
pip install -r requirements.txt

# 4. Environment file
copy .env.example .env           # macOS / Linux: cp .env.example .env

# 5. Database and first admin
python manage.py migrate
python manage.py createsuperuser

# 6. Run
python manage.py runserver
```

Open <http://127.0.0.1:8000/api/docs/> for the interactive documentation.

### Project structure

```
config/      settings, root URLs, pagination, shared helpers
accounts/    custom user (email login, roles), JWT auth, role permissions
events/      categories and events: CRUD, filters, image upload
bookings/    bookings, seat accounting, QR tickets, check-in, attendance
```

## Environment variables

Locally, the project reads its settings from a `.env` file next to `manage.py`.
This file is not pushed to GitHub. A minimal `.env` for local development:

```dotenv
# --- Core ---
DEBUG=True
SECRET_KEY='change-me-to-a-long-random-string'
ALLOWED_HOSTS=localhost,127.0.0.1

# --- Database ---
# Leave empty to use SQLite locally. In production this is the PostgreSQL URL.
DATABASE_URL=

# --- Booking rules ---
MAX_TICKETS_PER_BOOKING=5
```

Put the secret key in single quotes if it contains `$` or `#`.

In production, set the same variables in the hosting platform's dashboard.
All variables the project reads:

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | yes | none | Django secret key. Use a long random string. |
| `DEBUG` | no | `False` | `True` for local development only. |
| `ALLOWED_HOSTS` | no | `localhost,127.0.0.1` | Comma separated hostnames. The Railway domain is added automatically. |
| `DATABASE_URL` | production | local SQLite | PostgreSQL URL, e.g. `postgresql://user:pass@host:5432/db`. Leave empty locally. |
| `MAX_TICKETS_PER_BOOKING` | no | `5` | Highest ticket count allowed in one booking. Also the default for new events. |
| `DJANGO_SUPERUSER_EMAIL` | production | empty | Email of the admin created by `python manage.py ensure_admin` on deploy. Not needed locally if you use `createsuperuser`. |
| `DJANGO_SUPERUSER_PASSWORD` | production | empty | Password of that admin. |

Generate a secret key:

```bash
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

## Authentication flow

The API uses JSON Web Tokens (JWT). Users log in with **email and password**.

```
1. POST /api/auth/register/        creates the account, returns { user, access, refresh }
2. POST /api/auth/login/           returns { user, access, refresh }
3. Call protected endpoints with   Authorization: Bearer <access>
4. POST /api/auth/token/refresh/   when access expires, send { refresh } to get a new pair
5. POST /api/auth/logout/          send { refresh } to blacklist it
```

- The **access token** lives for 30 minutes and the **refresh token** for 7 days.
- Refresh tokens rotate: each refresh returns a new refresh token and blacklists the old one.
- The access token carries a `role` claim (`admin`, `organizer` or `user`).

Example:

```bash
# Register
curl -X POST http://127.0.0.1:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"email":"jane@example.com","password":"Str0ng-Passw0rd!","password_confirm":"Str0ng-Passw0rd!","first_name":"Jane"}'

# Log in
curl -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"jane@example.com","password":"Str0ng-Passw0rd!"}'

# Use the access token
curl http://127.0.0.1:8000/api/auth/me/ -H "Authorization: Bearer <access>"
```

In Swagger UI, press **Authorize** and paste the access token.

### Roles

| Action | Anonymous | User | Organizer | Admin |
|---|:-:|:-:|:-:|:-:|
| Browse events and categories | yes | yes | yes | yes |
| Book tickets, view and cancel own bookings | | yes | yes | yes |
| Create events | | | yes | yes |
| Update / delete events, upload image | | | own events | all |
| See bookings and attendance, check in attendees | | | own events | all |
| Manage categories | | | | yes |
| See, cancel and delete any booking | | | | yes |
| Manage users (role, active state) | | | | yes |

A new account registers as `user` (default) or `organizer`. Admin accounts are created with
`createsuperuser` / `ensure_admin`, or promoted by another admin.

## API endpoints

All list endpoints are paginated: `?page=2&page_size=20` (default 10, maximum 100).

### Auth

| Method | Endpoint | Access | Description |
|---|---|---|---|
| POST | `/api/auth/register/` | public | Create an account |
| POST | `/api/auth/login/` | public | Get access and refresh tokens |
| POST | `/api/auth/token/refresh/` | public | Refresh the token pair |
| POST | `/api/auth/logout/` | logged in | Blacklist the refresh token |
| GET, PATCH | `/api/auth/me/` | logged in | View / update own profile |
| POST | `/api/auth/change-password/` | logged in | Change own password |
| GET | `/api/auth/users/` | admin | List users (`?role=`, `?is_active=`, `?search=`) |
| GET, PATCH, DELETE | `/api/auth/users/{id}/` | admin | View, change role / active state, delete |

### Categories

| Method | Endpoint | Access | Description |
|---|---|---|---|
| GET | `/api/categories/` | public | List categories (`?search=`, `?ordering=name`) |
| POST | `/api/categories/` | admin | Create |
| GET | `/api/categories/{id}/` | public | Retrieve |
| PUT, PATCH | `/api/categories/{id}/` | admin | Update |
| DELETE | `/api/categories/{id}/` | admin | Delete (409 if it still has events) |

### Events

| Method | Endpoint | Access | Description |
|---|---|---|---|
| GET | `/api/events/` | public | List, search, filter, order, paginate |
| POST | `/api/events/` | organizer, admin | Create (JSON, or `multipart/form-data` with `image`) |
| GET | `/api/events/{id}/` | public | Retrieve |
| PUT, PATCH | `/api/events/{id}/` | owner, admin | Update |
| DELETE | `/api/events/{id}/` | owner, admin | Delete (409 if it has bookings) |
| GET | `/api/events/mine/` | organizer, admin | Events I organize, including drafts |
| PUT | `/api/events/{id}/image/` | owner, admin | Upload / replace the image (form field `image`) |
| DELETE | `/api/events/{id}/image/` | owner, admin | Remove the image |
| GET | `/api/events/{id}/bookings/` | owner, admin | Bookings of this event |
| GET | `/api/events/{id}/attendance/` | owner, admin | Attendance report |

Query parameters for `GET /api/events/`:

| Parameter | Example | Meaning |
|---|---|---|
| `search` | `?search=django` | Searches title, description, location and category name |
| `category`, `category_slug` | `?category=2` | By category |
| `location` | `?location=dhaka` | Location contains |
| `date` | `?date=2026-12-31` | Starts on this date |
| `starts_after`, `starts_before` | `?starts_after=2026-12-01T00:00:00Z` | Start time range |
| `min_price`, `max_price` | `?min_price=100&max_price=500` | Price range |
| `is_free` | `?is_free=true` | Free events only |
| `has_seats` | `?has_seats=true` | Not sold out |
| `upcoming` | `?upcoming=true` | Not started yet |
| `organizer` | `?organizer=3` | By organizer id |
| `ordering` | `?ordering=-price` | `start_time`, `price`, `created_at`, `available_seats`, `title` |
| `page`, `page_size` | `?page=2&page_size=20` | Pagination |

### Bookings and check-in

| Method | Endpoint | Access | Description |
|---|---|---|---|
| POST | `/api/bookings/` | logged in | Book tickets: `{ "event": 1, "quantity": 2 }` |
| GET | `/api/bookings/` | logged in | Own booking history. Admins see all (`?user=`, `?event=`, `?status=`) |
| GET | `/api/bookings/{id}/` | owner, event organizer, admin | Booking detail with embedded QR code |
| POST | `/api/bookings/{id}/cancel/` | owner, admin | Cancel and release the seats |
| DELETE | `/api/bookings/{id}/` | admin | Delete permanently |
| GET | `/api/bookings/{id}/qr-code/` | owner, event organizer, admin | Ticket QR code as a PNG image |
| POST | `/api/bookings/check-in/` | event organizer, admin | Check in: `{ "ticket_code": "<uuid from QR>" }` |

Booking rules:

- Only published events that have not started can be booked.
- `quantity` must be between 1 and the event's `max_tickets_per_booking` (default 5).
- Booking decreases `available_seats`; cancelling increases it again.
- Two people can never get the same last seat: the second request receives `409 Conflict`.
- Each QR code works once. A second scan returns `409 Conflict`.

### Other

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health/` | Health check |
| GET | `/api/docs/` | Swagger documentation |
| GET | `/api/schema/` | OpenAPI 3 schema |

### Status codes

| Code | Meaning |
|---|---|
| 400 | Validation error (bad input, ticket limit exceeded, event not bookable) |
| 401 | Missing or invalid token |
| 403 | Logged in, but the role is not allowed |
| 404 | Not found, or not visible to you |
| 409 | Conflict (not enough seats, already cancelled, ticket already used, item still in use) |

## Testing the API with Swagger

Open the live documentation at <https://biplobshil-innovativeskillsbdwebbatch09-ass-production.up.railway.app/api/docs/>,
or start the server
locally (`python manage.py runserver`) and open <http://127.0.0.1:8000/api/docs/>.
Follow the steps in order: each one uses something the previous step created.

**Using Swagger**

- **Call an endpoint:** click it, press **Try it out**, edit the body, press **Execute**.
- **Log in as someone:** copy the `access` value from a login or register response,
  press **Authorize** (top right), paste it, and press Authorize.
- **Switch account:** press **Authorize > Logout**, then paste another account's token.

The flow uses three accounts: the admin (created with `createsuperuser` locally, or `ensure_admin` on the live site), an organizer and
a normal user. An access token lasts 30 minutes; log in again if a request returns 401.
The ids below (category 1, event 1, bookings 1 and 2, user 3) assume a fresh database.

### 1. Health

`GET /api/health/` returns 200 `{"status": "ok"}`.

### 2. Auth: create accounts and log in

`POST /api/auth/register/` (organizer) returns 201:

```json
{"email": "organizer@example.com", "password": "Org-Pass-12345", "password_confirm": "Org-Pass-12345", "first_name": "Olive", "role": "organizer"}
```

`POST /api/auth/register/` (user) returns 201:

```json
{"email": "user@example.com", "password": "User-Pass-12345", "password_confirm": "User-Pass-12345", "first_name": "Jane"}
```

`POST /api/auth/login/` (admin) returns 200:

```json
{"email": "<admin email>", "password": "<admin password>"}
```

Authorize with the admin token. `GET /api/auth/me/` returns 200 with `"role": "admin"`.

### 3. Categories (as admin)

`POST /api/categories/` returns 201:

```json
{"name": "Tech", "description": "Tech talks and meetups"}
```

`GET /api/categories/` returns 200 with one result.

### 4. Events (as organizer)

Authorize with the organizer token. `POST /api/events/` returns 201 with `"available_seats": 50`:

```json
{"title": "Django Meetup", "category": 1, "location": "Dhaka", "start_time": "2026-12-20T18:00:00+06:00", "end_time": "2026-12-20T21:00:00+06:00", "price": "200.00", "total_seats": 50}
```

| Request | Expected |
|---|---|
| `PUT /api/events/1/image/` with a file in the `image` field | 200, `image` now has a URL |
| `GET /api/events/?search=django&ordering=-price&page_size=5` | 200 (search, ordering, pagination) |
| `GET /api/events/mine/` | 200 with the new event |

### 5. Bookings (as user)

Authorize with the user token. `POST /api/bookings/` returns 201; copy the `ticket_code`:

```json
{"event": 1, "quantity": 2}
```

| Request | Expected |
|---|---|
| `GET /api/events/1/` | `available_seats` is 48 |
| `GET /api/bookings/` | 200 with the booking history |
| `GET /api/bookings/1/qr-code/` | 200, the QR code image |
| `POST /api/bookings/` with `"quantity": 6` | 400, the limit is 5 tickets per booking |

### 6. Check-in (as organizer)

Authorize with the organizer token. `POST /api/bookings/check-in/`:

```json
{"ticket_code": "<ticket_code from step 5>"}
```

| Request | Expected |
|---|---|
| First call | 200 "Check-in successful", `checked_in_at` is set |
| Same call again | 409, a ticket works only once |
| `GET /api/events/1/attendance/` | 200 with the attendance report |
| `GET /api/events/1/bookings/` | 200 with the event's bookings |

### 7. Cancel (as user)

Authorize with the user token.

| Request | Expected |
|---|---|
| `POST /api/bookings/` with `{"event": 1, "quantity": 1}` | 201 (booking 2), seats are 47 |
| `POST /api/bookings/2/cancel/` | 200, `"status": "cancelled"` |
| `GET /api/events/1/` | `available_seats` is back to 48 |
| `POST /api/bookings/2/cancel/` again | 409, already cancelled |
| `POST /api/bookings/1/cancel/` | 409, the ticket was already checked in |

### 8. Role permissions (as user)

| Request | Expected |
|---|---|
| `POST /api/categories/` | 403 |
| `POST /api/events/` | 403 |
| `POST /api/bookings/check-in/` | 403 |
| `GET /api/auth/users/` | 403 |
| `GET /api/bookings/` after **Authorize > Logout** | 401 |

### 9. Admin management (as admin)

Authorize with the admin token.

| Request | Expected |
|---|---|
| `GET /api/auth/users/` | 200 with all three users |
| `PATCH /api/auth/users/3/` with `{"role": "organizer"}` | 200 |
| `GET /api/bookings/` | 200 with every user's bookings |
| `DELETE /api/bookings/2/` | 204 |
| `DELETE /api/events/1/` | 409, the event still has a booking |

### 10. Refresh and logout

| Request | Expected |
|---|---|
| `POST /api/auth/token/refresh/` with `{"refresh": "<refresh token>"}` | 200 with a new token pair |
| `POST /api/auth/logout/` with `{"refresh": "<the new refresh token>"}` | 200 |
| `POST /api/auth/token/refresh/` with that same token | 401, it is blacklisted |

## Deployment

GatherHub is deployed on Railway with PostgreSQL, at
<https://biplobshil-innovativeskillsbdwebbatch09-ass-production.up.railway.app>. The frontend at <https://drf.biplobshil.online/> calls this API.

1. Push the repository to GitHub.
2. On Railway: **New Project > Deploy from GitHub repo**, then add **Database > PostgreSQL**.
3. On the web service, add these variables:
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`
   - `SECRET_KEY` = a long random string
   - `DEBUG` = `False`
   - `DJANGO_SUPERUSER_EMAIL`, `DJANGO_SUPERUSER_PASSWORD`
4. **Settings > Networking > Generate Domain**.

`railway.json` runs the migrations, collects static files, creates the admin and starts gunicorn.

Uploaded images are stored on the server's disk. On Railway this disk is reset on each
redeploy unless a volume is attached.
