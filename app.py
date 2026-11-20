"""Fleet Management System: tractor onboarding -> loading -> transit -> customer unloading.

Run:  python app.py        (creates fleet.db with demo data on first run)
      python app.py --reset (deletes and recreates the database)
"""

import functools
import math
import os
import random
import sqlite3
import sys
from datetime import date, datetime, timedelta

from flask import (
    Flask,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "fleet.db")
GEOFENCE_METERS = 300

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-in-production")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def q(sql, args=(), one=False):
    rows = get_db().execute(sql, args).fetchall()
    if one:
        return rows[0] if rows else None
    return rows


def run(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db(reset=False):
    if reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    if os.path.exists(DB_PATH):
        return
    db = sqlite3.connect(DB_PATH)
    with open(os.path.join(APP_DIR, "schema.sql")) as f:
        db.executescript(f.read())

    def user(name, email, mobile, pw, role):
        return db.execute(
            "INSERT INTO users(name,email,mobile,password_hash,role) VALUES(?,?,?,?,?)",
            (name, email, mobile, generate_password_hash(pw), role),
        ).lastrowid

    admin = user("Fleet Admin", "admin@fleet.com", "9000000001", "admin123", "admin")
    user(
        "Dispatcher Ravi",
        "dispatcher@fleet.com",
        "9000000002",
        "dispatch123",
        "dispatcher",
    )
    d1 = user("Driver Suresh", "driver1@fleet.com", "9000000003", "driver123", "driver")
    d2 = user("Driver Mahesh", "driver2@fleet.com", "9000000004", "driver123", "driver")
    c1 = user(
        "Customer Anil", "customer@fleet.com", "9000000005", "customer123", "customer"
    )
    db.execute(
        "INSERT INTO drivers(user_id,license_no,license_expiry) VALUES(?,?,?)",
        (d1, "AP37-2019-0012345", "2029-06-30"),
    )
    db.execute(
        "INSERT INTO drivers(user_id,license_no,license_expiry) VALUES(?,?,?)",
        (d2, "AP37-2020-0054321", "2030-01-15"),
    )
    cust = db.execute(
        "INSERT INTO customers(user_id,company,address) VALUES(?,?,?)",
        (c1, "Anil Constructions", "Eluru, Andhra Pradesh"),
    ).lastrowid

    t1 = db.execute(
        "INSERT INTO tractors(reg_no,make,model,chassis_no,engine_no,capacity_tons,"
        "gps_device_id,status,approved_by) VALUES(?,?,?,?,?,?,?,?,?)",
        (
            "AP37TA1001",
            "Tata",
            "Prima 4028.S",
            "CH1001",
            "EN1001",
            28,
            "GPS-0001",
            "Available",
            admin,
        ),
    ).lastrowid
    db.execute(
        "INSERT INTO tractors(reg_no,make,model,chassis_no,engine_no,capacity_tons,"
        "gps_device_id,status,approved_by) VALUES(?,?,?,?,?,?,?,?,?)",
        (
            "AP37TA1002",
            "Ashok Leyland",
            "4220",
            "CH1002",
            "EN1002",
            25,
            "GPS-0002",
            "Available",
            admin,
        ),
    )
    db.execute(
        "INSERT INTO tractors(reg_no,make,model,chassis_no,engine_no,capacity_tons,gps_device_id)"
        " VALUES(?,?,?,?,?,?,?)",
        ("AP37TA1003", "BharatBenz", "3528C", "CH1003", "EN1003", 28, "GPS-0003"),
    )
    soon = (date.today() + timedelta(days=12)).isoformat()
    later = (date.today() + timedelta(days=300)).isoformat()
    for dt, num, exp in [
        ("RC", "RC-1001", later),
        ("Insurance", "INS-7781", soon),
        ("Fitness", "FIT-221", later),
        ("Permit", "PER-909", later),
        ("Pollution", "PUC-554", later),
    ]:
        db.execute(
            "INSERT INTO tractor_documents(tractor_id,doc_type,doc_number,expiry_date)"
            " VALUES(?,?,?,?)",
            (t1, dt, num, exp),
        )
    db.execute(
        "INSERT INTO orders(customer_id,pickup_location,pickup_lat,pickup_lng,drop_location,"
        "drop_lat,drop_lng,material,quantity,unit,created_by) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (
            cust,
            "Vijayawada Stockyard",
            16.5062,
            80.6480,
            "Eluru Site-A",
            16.7107,
            81.0952,
            "Cement",
            20,
            "tons",
            c1,
        ),
    )
    db.commit()
    db.close()


# ---------------------------------------------------------------- auth
@app.before_request
def load_user():
    uid = session.get("user_id")
    g.user = (
        q("SELECT * FROM users WHERE id=? AND active=1", (uid,), one=True)
        if uid
        else None
    )


def login_required(*roles):
    def deco(f):
        @functools.wraps(f)
        def wrapper(*a, **kw):
            if not g.user:
                return redirect(url_for("login", next=request.path))
            if roles and g.user["role"] not in roles:
                abort(403)
            return f(*a, **kw)

        return wrapper

    return deco


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        u = q(
            "SELECT * FROM users WHERE lower(email)=? AND active=1", (email,), one=True
        )
        if u and check_password_hash(u["password_hash"], request.form["password"]):
            session.clear()
            session["user_id"] = u["id"]
            nxt = request.args.get("next", "")
            return redirect(
                nxt
                if nxt.startswith("/") and not nxt.startswith("//")
                else url_for("home")
            )
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required()
def home():
    target = {
        "admin": "dashboard",
        "dispatcher": "dashboard",
        "driver": "driver_home",
        "customer": "customer_home",
    }[g.user["role"]]
    return redirect(url_for(target))


@app.errorhandler(403)
def forbidden(_e):
    return render_template(
        "message.html", title="Access denied", text="Your role cannot open this page."
    ), 403


# ---------------------------------------------------------------- helpers
TRIP_SELECT = """
SELECT tr.*, o.pickup_location, o.drop_location, o.material, o.quantity, o.unit,
       o.pickup_lat, o.pickup_lng, o.drop_lat, o.drop_lng, o.customer_id,
       t.reg_no, t.make, t.model, du.name AS driver_name, cu.name AS customer_name,
       d.user_id AS driver_user_id, c.user_id AS customer_user_id
FROM trips tr
JOIN orders o ON o.id = tr.order_id
JOIN tractors t ON t.id = tr.tractor_id
JOIN drivers d ON d.id = tr.driver_id
JOIN users du ON du.id = d.user_id
JOIN customers c ON c.id = o.customer_id
JOIN users cu ON cu.id = c.user_id
"""


def my_driver():
    return q("SELECT * FROM drivers WHERE user_id=?", (g.user["id"],), one=True)


def my_customer():
    return q("SELECT * FROM customers WHERE user_id=?", (g.user["id"],), one=True)


def get_trip_or_404(trip_id):
    trip = q(TRIP_SELECT + " WHERE tr.id=?", (trip_id,), one=True)
    if not trip:
        abort(404)
    role = g.user["role"]
    if role == "driver" and trip["driver_user_id"] != g.user["id"]:
        abort(403)
    if role == "customer" and trip["customer_user_id"] != g.user["id"]:
        abort(403)
    return trip


def set_status(trip, new_status, note=""):
    run("UPDATE trips SET status=? WHERE id=?", (new_status, trip["id"]))
    run("UPDATE orders SET status=? WHERE id=?", (new_status, trip["order_id"]))
    run(
        "INSERT INTO trip_status_log(trip_id,status,changed_by,note,changed_at) VALUES(?,?,?,?,?)",
        (trip["id"], new_status, g.user["id"] if g.get("user") else None, note, now()),
    )
    if new_status == "Closed":
        run("UPDATE trips SET closed_at=? WHERE id=?", (now(), trip["id"]))
        run("UPDATE tractors SET status='Available' WHERE id=?", (trip["tractor_id"],))
        run("UPDATE drivers SET status='Available' WHERE id=?", (trip["driver_id"],))


def haversine_m(lat1, lng1, lat2, lng2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def to_float(v):
    if v is None or str(v).strip() == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- dashboard
@app.route("/dashboard")
@login_required("admin", "dispatcher")
def dashboard():
    count = lambda sql: q(sql, one=True)[0]
    stats = {
        "Tractors": count("SELECT COUNT(*) FROM tractors"),
        "Available": count("SELECT COUNT(*) FROM tractors WHERE status='Available'"),
        "Pending approval": count(
            "SELECT COUNT(*) FROM tractors WHERE status='Pending'"
        ),
        "New orders": count("SELECT COUNT(*) FROM orders WHERE status='New'"),
        "Active trips": count("SELECT COUNT(*) FROM trips WHERE status!='Closed'"),
    }
    expiring = q("""SELECT d.*, t.reg_no FROM tractor_documents d JOIN tractors t ON t.id=d.tractor_id
                    WHERE d.expiry_date <= date('now','+30 day') ORDER BY d.expiry_date""")
    active = q(TRIP_SELECT + " WHERE tr.status!='Closed' ORDER BY tr.id DESC")
    new_orders = q("""SELECT o.*, u.name AS customer_name FROM orders o
                      JOIN customers c ON c.id=o.customer_id JOIN users u ON u.id=c.user_id
                      WHERE o.status='New' ORDER BY o.id""")
    return render_template(
        "dashboard.html",
        stats=stats,
        expiring=expiring,
        active=active,
        new_orders=new_orders,
        today=date.today().isoformat(),
    )


# ---------------------------------------------------------------- tractors
@app.route("/tractors")
@login_required("admin", "dispatcher")
def tractors():
    return render_template(
        "tractors.html", rows=q("SELECT * FROM tractors ORDER BY id DESC")
    )


@app.route("/tractors/new", methods=["GET", "POST"])
@login_required("admin")
def tractor_new():
    if request.method == "POST":
        f = request.form
        try:
            tid = run(
                """INSERT INTO tractors(reg_no,make,model,chassis_no,engine_no,capacity_tons,gps_device_id)
                         VALUES(?,?,?,?,?,?,?)""",
                (
                    f["reg_no"].strip().upper(),
                    f["make"],
                    f["model"],
                    f["chassis_no"],
                    f["engine_no"],
                    to_float(f["capacity_tons"]),
                    f["gps_device_id"],
                ),
            )
        except sqlite3.IntegrityError:
            flash("A tractor with this registration number already exists.", "error")
            return render_template("tractor_form.html")
        flash("Tractor onboarded. Add documents, then approve it.", "ok")
        return redirect(url_for("tractor_detail", tid=tid))
    return render_template("tractor_form.html")


@app.route("/tractors/<int:tid>")
@login_required("admin", "dispatcher")
def tractor_detail(tid):
    t = q("SELECT * FROM tractors WHERE id=?", (tid,), one=True) or abort(404)
    docs = q(
        "SELECT * FROM tractor_documents WHERE tractor_id=? ORDER BY expiry_date",
        (tid,),
    )
    return render_template(
        "tractor_detail.html", t=t, docs=docs, today=date.today().isoformat()
    )


@app.route("/tractors/<int:tid>/docs", methods=["POST"])
@login_required("admin")
def tractor_doc_add(tid):
    f = request.form
    run(
        "INSERT INTO tractor_documents(tractor_id,doc_type,doc_number,expiry_date) VALUES(?,?,?,?)",
        (tid, f["doc_type"], f["doc_number"], f["expiry_date"]),
    )
    flash("Document added.", "ok")
    return redirect(url_for("tractor_detail", tid=tid))


@app.route("/tractors/<int:tid>/approve", methods=["POST"])
@login_required("admin")
def tractor_approve(tid):
    t = q("SELECT * FROM tractors WHERE id=?", (tid,), one=True) or abort(404)
    docs = q("SELECT * FROM tractor_documents WHERE tractor_id=?", (tid,))
    if not docs:
        flash("Add at least one document before approving.", "error")
    elif any(d["expiry_date"] < date.today().isoformat() for d in docs):
        flash(
            "A document has expired. Add a renewed one or remove the expired record first.",
            "error",
        )
    elif t["status"] == "Pending":
        run(
            "UPDATE tractors SET status='Available', approved_by=? WHERE id=?",
            (g.user["id"], tid),
        )
        flash("Tractor approved and now Available.", "ok")
    return redirect(url_for("tractor_detail", tid=tid))


@app.route("/docs/<int:did>/delete", methods=["POST"])
@login_required("admin")
def doc_delete(did):
    d = q("SELECT * FROM tractor_documents WHERE id=?", (did,), one=True) or abort(404)
    run("DELETE FROM tractor_documents WHERE id=?", (did,))
    return redirect(url_for("tractor_detail", tid=d["tractor_id"]))


# ---------------------------------------------------------------- drivers & customers
@app.route("/drivers")
@login_required("admin", "dispatcher")
def drivers():
    rows = q("""SELECT d.*, u.name, u.email, u.mobile FROM drivers d JOIN users u ON u.id=d.user_id
                ORDER BY d.id DESC""")
    return render_template("people.html", kind="driver", rows=rows)


@app.route("/customers")
@login_required("admin", "dispatcher")
def customers():
    rows = q("""SELECT c.*, u.name, u.email, u.mobile FROM customers c JOIN users u ON u.id=c.user_id
                ORDER BY c.id DESC""")
    return render_template("people.html", kind="customer", rows=rows)


@app.route("/<kind>s/new", methods=["GET", "POST"])
@login_required("admin")
def person_new(kind):
    if kind not in ("driver", "customer"):
        abort(404)
    if request.method == "POST":
        f = request.form
        try:
            uid = run(
                "INSERT INTO users(name,email,mobile,password_hash,role) VALUES(?,?,?,?,?)",
                (
                    f["name"],
                    f["email"].strip().lower(),
                    f["mobile"],
                    generate_password_hash(f["password"]),
                    kind,
                ),
            )
        except sqlite3.IntegrityError:
            flash("That email is already registered.", "error")
            return render_template("person_form.html", kind=kind)
        if kind == "driver":
            run(
                "INSERT INTO drivers(user_id,license_no,license_expiry) VALUES(?,?,?)",
                (uid, f["license_no"], f["license_expiry"]),
            )
        else:
            run(
                "INSERT INTO customers(user_id,company,address) VALUES(?,?,?)",
                (uid, f["company"], f["address"]),
            )
        flash(f"{kind.title()} created. They can now log in.", "ok")
        return redirect(url_for(kind + "s"))
    return render_template("person_form.html", kind=kind)


# ---------------------------------------------------------------- orders
@app.route("/orders")
@login_required("admin", "dispatcher")
def orders():
    rows = q("""SELECT o.*, u.name AS customer_name FROM orders o
                JOIN customers c ON c.id=o.customer_id JOIN users u ON u.id=c.user_id
                ORDER BY o.id DESC""")
    return render_template("orders.html", rows=rows)


@app.route("/orders/new", methods=["GET", "POST"])
@login_required("admin", "dispatcher", "customer")
def order_new():
    customers_list = q(
        "SELECT c.id, u.name FROM customers c JOIN users u ON u.id=c.user_id"
    )
    if request.method == "POST":
        f = request.form
        cust = (
            my_customer()["id"]
            if g.user["role"] == "customer"
            else int(f["customer_id"])
        )
        run(
            """INSERT INTO orders(customer_id,pickup_location,pickup_lat,pickup_lng,drop_location,
               drop_lat,drop_lng,material,quantity,unit,created_by) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                cust,
                f["pickup_location"],
                to_float(f["pickup_lat"]),
                to_float(f["pickup_lng"]),
                f["drop_location"],
                to_float(f["drop_lat"]),
                to_float(f["drop_lng"]),
                f["material"],
                to_float(f["quantity"]) or 0,
                f["unit"],
                g.user["id"],
            ),
        )
        flash("Order created.", "ok")
        return redirect(
            url_for("home") if g.user["role"] == "customer" else url_for("orders")
        )
    return render_template("order_form.html", customers=customers_list)


@app.route("/orders/<int:oid>/assign", methods=["GET", "POST"])
@login_required("admin", "dispatcher")
def assign(oid):
    o = q(
        """SELECT o.*, u.name AS customer_name FROM orders o JOIN customers c ON c.id=o.customer_id
             JOIN users u ON u.id=c.user_id WHERE o.id=?""",
        (oid,),
        one=True,
    ) or abort(404)
    if o["status"] != "New":
        flash("This order is already assigned.", "error")
        return redirect(url_for("orders"))
    free_tractors = q("SELECT * FROM tractors WHERE status='Available' ORDER BY reg_no")
    free_drivers = q("""SELECT d.id, u.name, d.license_no FROM drivers d JOIN users u ON u.id=d.user_id
                        WHERE d.status='Available' AND u.active=1""")
    if request.method == "POST":
        tid, did = int(request.form["tractor_id"]), int(request.form["driver_id"])
        otp = f"{random.randint(0, 9999):04d}"
        trip_id = run(
            "INSERT INTO trips(order_id,tractor_id,driver_id,delivery_otp) VALUES(?,?,?,?)",
            (oid, tid, did, otp),
        )
        run("UPDATE tractors SET status='On Trip' WHERE id=?", (tid,))
        run("UPDATE drivers SET status='On Trip' WHERE id=?", (did,))
        set_status(
            {"id": trip_id, "order_id": oid}, "Assigned", "Tractor and driver assigned"
        )
        flash("Trip created and assigned.", "ok")
        return redirect(url_for("trip_detail", trip_id=trip_id))
    return render_template(
        "assign.html", o=o, tractors=free_tractors, drivers=free_drivers
    )


# ---------------------------------------------------------------- trips
ACTIONS = {
    "start_loading": dict(
        label="Start loading",
        frm="Assigned",
        to="Loading",
        roles=("admin", "dispatcher"),
    ),
    "finish_loading": dict(
        label="Finish loading",
        frm="Loading",
        to="Loaded",
        roles=("admin", "dispatcher"),
        form="loading",
    ),
    "start_transit": dict(
        label="Start trip", frm="Loaded", to="In Transit", roles=("driver",)
    ),
    "arrived": dict(
        label="Mark arrived", frm="In Transit", to="Arrived", roles=("driver",)
    ),
    "start_unloading": dict(
        label="Start unloading", frm="Arrived", to="Unloading", roles=("driver",)
    ),
    "confirm_delivery": dict(
        label="Confirm delivery",
        frm="Unloading",
        to="Delivered",
        roles=("driver",),
        form="unloading",
    ),
    "close": dict(
        label="Close trip", frm="Delivered", to="Closed", roles=("admin", "dispatcher")
    ),
}
STATUS_CHAIN = [
    "Assigned",
    "Loading",
    "Loaded",
    "In Transit",
    "Arrived",
    "Unloading",
    "Delivered",
    "Closed",
]


@app.route("/trips")
@login_required("admin", "dispatcher")
def trips():
    return render_template("trips.html", rows=q(TRIP_SELECT + " ORDER BY tr.id DESC"))


@app.route("/trips/<int:trip_id>")
@login_required()
def trip_detail(trip_id):
    trip = get_trip_or_404(trip_id)
    allowed = {
        k: v
        for k, v in ACTIONS.items()
        if v["frm"] == trip["status"] and g.user["role"] in v["roles"]
    }
    return render_template(
        "trip_detail.html",
        trip=trip,
        actions=allowed,
        chain=STATUS_CHAIN,
        log=q(
            """SELECT l.*, u.name AS who FROM trip_status_log l LEFT JOIN users u ON u.id=l.changed_by
                 WHERE trip_id=? ORDER BY l.id""",
            (trip_id,),
        ),
        loading=q(
            "SELECT * FROM loading_records WHERE trip_id=?", (trip_id,), one=True
        ),
        unloading=q(
            "SELECT * FROM unloading_records WHERE trip_id=?", (trip_id,), one=True
        ),
    )


@app.route("/trips/<int:trip_id>/action/<name>", methods=["POST"])
@login_required()
def trip_action(trip_id, name):
    trip = get_trip_or_404(trip_id)
    act = ACTIONS.get(name) or abort(404)
    if g.user["role"] not in act["roles"] or trip["status"] != act["frm"]:
        flash("That action is not available right now.", "error")
        return redirect(url_for("trip_detail", trip_id=trip_id))
    f = request.form

    if name == "start_loading":
        run(
            "INSERT OR REPLACE INTO loading_records(trip_id,started_at,recorded_by) VALUES(?,?,?)",
            (trip_id, now(), g.user["id"]),
        )
    elif name == "finish_loading":
        run(
            """UPDATE loading_records SET ended_at=?, loaded_qty=?, weight_kg=?, seal_no=?, notes=?
               WHERE trip_id=?""",
            (
                now(),
                to_float(f.get("loaded_qty")),
                to_float(f.get("weight_kg")),
                f.get("seal_no"),
                f.get("notes"),
                trip_id,
            ),
        )
    elif name == "start_unloading":
        run(
            "INSERT OR REPLACE INTO unloading_records(trip_id,started_at) VALUES(?,?)",
            (trip_id, now()),
        )
    elif name == "confirm_delivery":
        if f.get("otp", "").strip() != trip["delivery_otp"]:
            flash(
                "Wrong delivery OTP. Ask the customer for the 4-digit code shown in their portal.",
                "error",
            )
            return redirect(url_for("trip_detail", trip_id=trip_id))
        run(
            """UPDATE unloading_records SET ended_at=?, received_qty=?, receiver_name=?, otp_verified=1,
               notes=? WHERE trip_id=?""",
            (
                now(),
                to_float(f.get("received_qty")),
                f.get("receiver_name"),
                f.get("notes"),
                trip_id,
            ),
        )

    set_status(trip, act["to"], f.get("notes", "") if act.get("form") else "")
    flash(f"Status updated: {act['to']}.", "ok")
    return redirect(url_for("trip_detail", trip_id=trip_id))


# ---------------------------------------------------------------- driver / customer homes
@app.route("/driver")
@login_required("driver")
def driver_home():
    rows = q(
        TRIP_SELECT + " WHERE tr.driver_id=? ORDER BY tr.id DESC", (my_driver()["id"],)
    )
    return render_template("my.html", title="My trips", rows=rows)


@app.route("/customer")
@login_required("customer")
def customer_home():
    rows = q(
        TRIP_SELECT + " WHERE o.customer_id=? ORDER BY tr.id DESC",
        (my_customer()["id"],),
    )
    pending = q(
        "SELECT * FROM orders WHERE customer_id=? AND status='New' ORDER BY id DESC",
        (my_customer()["id"],),
    )
    return render_template("my.html", title="My shipments", rows=rows, pending=pending)


# ---------------------------------------------------------------- GPS API
@app.route("/api/trips/<int:trip_id>/location", methods=["POST"])
@login_required("driver")
def api_post_location(trip_id):
    trip = get_trip_or_404(trip_id)
    data = request.get_json(silent=True) or {}
    lat, lng = to_float(data.get("lat")), to_float(data.get("lng"))
    if lat is None or lng is None or not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return jsonify(error="lat/lng required"), 400
    if trip["status"] in ("Assigned", "Closed", "Delivered"):
        return jsonify(error="trip is not active"), 409
    run(
        "INSERT INTO gps_locations(trip_id,tractor_id,lat,lng,speed,recorded_at) VALUES(?,?,?,?,?,?)",
        (trip_id, trip["tractor_id"], lat, lng, to_float(data.get("speed")), now()),
    )
    auto_arrived = False
    if trip["status"] == "In Transit" and trip["drop_lat"] is not None:
        if haversine_m(lat, lng, trip["drop_lat"], trip["drop_lng"]) <= GEOFENCE_METERS:
            set_status(trip, "Arrived", "Geofence: entered customer site")
            auto_arrived = True
    return jsonify(ok=True, auto_arrived=auto_arrived)


@app.route("/api/trips/<int:trip_id>/locations")
@login_required()
def api_get_locations(trip_id):
    trip = get_trip_or_404(trip_id)
    pts = q(
        "SELECT lat,lng,speed,recorded_at FROM gps_locations WHERE trip_id=? ORDER BY id DESC LIMIT 300",
        (trip_id,),
    )
    return jsonify(status=trip["status"], points=[dict(p) for p in reversed(pts)])


if __name__ == "__main__":
    init_db(reset="--reset" in sys.argv)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
else:
    init_db()
