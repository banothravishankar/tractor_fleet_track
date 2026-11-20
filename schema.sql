-- Fleet Management System: SQLite schema
PRAGMA foreign_keys = ON;

CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  mobile TEXT,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK (
    role IN ('admin', 'dispatcher', 'driver', 'customer')
  ),
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE tractors (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  reg_no TEXT NOT NULL UNIQUE,
  make TEXT,
  model TEXT,
  chassis_no TEXT,
  engine_no TEXT,
  capacity_tons REAL,
  gps_device_id TEXT,
  status TEXT NOT NULL DEFAULT 'Pending' CHECK (
    status IN ('Pending', 'Available', 'On Trip', 'Inactive')
  ),
  approved_by INTEGER REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE tractor_documents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tractor_id INTEGER NOT NULL REFERENCES tractors(id) ON DELETE CASCADE,
  doc_type TEXT NOT NULL,
  doc_number TEXT,
  expiry_date TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE drivers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
  license_no TEXT,
  license_expiry TEXT,
  status TEXT NOT NULL DEFAULT 'Available' CHECK (status IN ('Available', 'On Trip'))
);

CREATE TABLE customers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
  company TEXT,
  address TEXT
);

CREATE TABLE orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  customer_id INTEGER NOT NULL REFERENCES customers(id),
  pickup_location TEXT NOT NULL,
  pickup_lat REAL,
  pickup_lng REAL,
  drop_location TEXT NOT NULL,
  drop_lat REAL,
  drop_lng REAL,
  material TEXT NOT NULL,
  quantity REAL NOT NULL,
  unit TEXT NOT NULL DEFAULT 'tons',
  status TEXT NOT NULL DEFAULT 'New',
  created_by INTEGER REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE trips (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL UNIQUE REFERENCES orders(id),
  tractor_id INTEGER NOT NULL REFERENCES tractors(id),
  driver_id INTEGER NOT NULL REFERENCES drivers(id),
  status TEXT NOT NULL DEFAULT 'Assigned',
  delivery_otp TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  closed_at TEXT
);

CREATE TABLE trip_status_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
  status TEXT NOT NULL,
  changed_by INTEGER REFERENCES users(id),
  note TEXT,
  changed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE loading_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trip_id INTEGER NOT NULL UNIQUE REFERENCES trips(id) ON DELETE CASCADE,
  started_at TEXT,
  ended_at TEXT,
  loaded_qty REAL,
  weight_kg REAL,
  seal_no TEXT,
  notes TEXT,
  recorded_by INTEGER REFERENCES users(id)
);

CREATE TABLE unloading_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trip_id INTEGER NOT NULL UNIQUE REFERENCES trips(id) ON DELETE CASCADE,
  started_at TEXT,
  ended_at TEXT,
  received_qty REAL,
  receiver_name TEXT,
  otp_verified INTEGER NOT NULL DEFAULT 0,
  notes TEXT
);

CREATE TABLE gps_locations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
  tractor_id INTEGER NOT NULL REFERENCES tractors(id),
  lat REAL NOT NULL,
  lng REAL NOT NULL,
  speed REAL,
  recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_gps_trip ON gps_locations (trip_id, id);

CREATE INDEX idx_trips_status ON trips (status);

CREATE INDEX idx_docs_expiry ON tractor_documents (expiry_date);