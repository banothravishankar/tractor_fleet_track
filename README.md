# FleetTrack: Tractor Onboarding → Loading → Delivery → Unloading

A role-based web portal with login, built with Flask + SQLite (no database server needed).

## Run it

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000. The database `fleet.db` is included with demo data
(`python app.py --reset` recreates it).

## Demo logins

| Role | Email | Password |
|---|---|---|
| Admin | admin@fleet.com | admin123 |
| Dispatcher | dispatcher@fleet.com | dispatch123 |
| Driver | driver1@fleet.com | driver123 |
| Customer | customer@fleet.com | customer123 |

## Try the full workflow (about 3 minutes)

1. **Admin**: Tractors → Onboard tractor → add documents → Approve (becomes *Available*).
2. **Customer**: New order (add pickup/drop latitude and longitude to enable the map and geofence).
   Seed order #1 (Vijayawada → Eluru) is already waiting.
3. **Dispatcher**: Dashboard → Assign → choose an available tractor and driver.
4. **Dispatcher**: open the trip → Start loading → Finish loading (weight, seal number).
5. **Driver**: Start trip → "Simulate drive (demo)". The customer's trip page shows the live map.
   Entering the 300 m geofence of the drop point marks the trip *Arrived* automatically.
6. **Driver**: Start unloading. **Customer**: read the 4-digit delivery OTP on the trip page and tell the driver.
7. **Driver**: Confirm delivery (OTP + received quantity + receiver name) → *Delivered*.
8. **Dispatcher/Admin**: Close trip → tractor and driver become *Available* again.

Status chain: Assigned → Loading → Loaded → In Transit → Arrived → Unloading → Delivered → Closed.
Every change is stored in `trip_status_log` with time and user.

## Roles

- **Admin**: everything, plus onboarding tractors, drivers and customers and approving tractors.
- **Dispatcher**: orders, assignment, loading, closing trips.
- **Driver**: only their own trips (start trip, GPS, arrival, unloading, OTP confirm).
- **Customer**: only their own orders and shipments, live map, delivery OTP.

## Files

- `app.py`: routes, workflow rules, GPS API, geofence
- `schema.sql`: SQLite schema (used by the app)
- `schema_postgres.sql`: same schema for PostgreSQL (production)
- `templates/`, `static/`: pages and styling
- `test_flow.py`: automated end-to-end test (`python test_flow.py`)

## Tables

`users`, `tractors`, `tractor_documents`, `drivers`, `customers`, `orders`, `trips`,
`trip_status_log`, `loading_records`, `unloading_records`, `gps_locations`

## Before real use

- Set a strong `SECRET_KEY` environment variable and change all demo passwords.
- Run behind HTTPS with a production server (e.g. `gunicorn app:app`), not the dev server.
- Add CSRF protection (Flask-WTF) and login rate limiting.
- The delivery OTP is shown in the customer portal. To send it by SMS, plug an SMS provider in
  where the trip is assigned.
- The map uses OpenStreetMap tiles and Leaflet from a CDN, so it needs internet access in the browser.
- For many vehicles, move to PostgreSQL (`schema_postgres.sql`) and the Kafka/Redis architecture
  from the reference design; the GPS endpoint here is the single ingestion point to replace.
