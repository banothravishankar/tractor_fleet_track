CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  mobile TEXT,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK (
    role IN ('admin', 'dispatcher', 'driver', 'customer')
  ),
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE tractors (
  id SERIAL PRIMARY KEY,
  reg_no TEXT NOT NULL UNIQUE,
  make TEXT,
  model TEXT,
  chassis_no TEXT,
  engine_no TEXT,
  capacity_tons DOUBLE PRECISION,
  gps_device_id TEXT,
  status TEXT NOT NULL DEFAULT 'Pending' CHECK (
    status IN ('Pending', 'Available', 'On Trip', 'Inactive')
  ),
  approved_by INTEGER REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE tractor_documents (
  id SERIAL PRIMARY KEY,
  tractor_id INTEGER NOT NULL REFERENCES tractors(id) ON DELETE CASCADE,
  doc_type TEXT NOT NULL,
  doc_number TEXT,
  expiry_date DATE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE drivers (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
  license_no TEXT,
  license_expiry DATE,
  status TEXT NOT NULL DEFAULT 'Available' CHECK (status IN ('Available', 'On Trip'))
);

CREATE TABLE customers (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
  company TEXT,
  address TEXT
);

CREATE TABLE orders (
  id SERIAL PRIMARY KEY,
  customer_id INTEGER NOT NULL REFERENCES customers(id),
  pickup_location TEXT NOT NULL,
  pickup_lat DOUBLE PRECISION,
  pickup_lng DOUBLE PRECISION,
  drop_location TEXT NOT NULL,
  drop_lat DOUBLE PRECISION,
  drop_lng DOUBLE PRECISION,
  material TEXT NOT NULL,
  quantity DOUBLE PRECISION NOT NULL,
  unit TEXT NOT NULL DEFAULT 'tons',
  status TEXT NOT NULL DEFAULT 'New',
  created_by INTEGER REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE trips (
  id SERIAL PRIMARY KEY,
  order_id INTEGER NOT NULL UNIQUE REFERENCES orders(id),
  tractor_id INTEGER NOT NULL REFERENCES tractors(id),
  driver_id INTEGER NOT NULL REFERENCES drivers(id),
  status TEXT NOT NULL DEFAULT 'Assigned',
  delivery_otp TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  closed_at TIMESTAMPTZ
);

CREATE TABLE trip_status_log (
  id SERIAL PRIMARY KEY,
  trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
  status TEXT NOT NULL,
  changed_by INTEGER REFERENCES users(id),
  note TEXT,
  changed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE loading_records (
  id SERIAL PRIMARY KEY,
  trip_id INTEGER NOT NULL UNIQUE REFERENCES trips(id) ON DELETE CASCADE,
  started_at TIMESTAMPTZ,
  ended_at TIMESTAMPTZ,
  loaded_qty DOUBLE PRECISION,
  weight_kg DOUBLE PRECISION,
  seal_no TEXT,
  notes TEXT,
  recorded_by INTEGER REFERENCES users(id)
);

CREATE TABLE unloading_records (
  id SERIAL PRIMARY KEY,
  trip_id INTEGER NOT NULL UNIQUE REFERENCES trips(id) ON DELETE CASCADE,
  started_at TIMESTAMPTZ,
  ended_at TIMESTAMPTZ,
  received_qty DOUBLE PRECISION,
  receiver_name TEXT,
  otp_verified BOOLEAN NOT NULL DEFAULT FALSE,
  notes TEXT
);

CREATE TABLE gps_locations (
  id BIGSERIAL PRIMARY KEY,
  trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
  tractor_id INTEGER NOT NULL REFERENCES tractors(id),
  lat DOUBLE PRECISION NOT NULL,
  lng DOUBLE PRECISION NOT NULL,
  speed DOUBLE PRECISION,
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_gps_trip ON gps_locations (trip_id, id);

CREATE INDEX idx_trips_status ON trips (status);

CREATE INDEX idx_docs_expiry ON tractor_documents (expiry_date);