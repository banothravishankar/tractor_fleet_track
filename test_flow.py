"""Smoke test: runs the full tractor-to-unloading workflow through the web app."""

import os, re, tempfile
import app as fleet

fleet.DB_PATH = os.path.join(tempfile.mkdtemp(), "test.db")
fleet.init_db(reset=True)


def client(email, pw):
    c = fleet.app.test_client()
    r = c.post("/login", data={"email": email, "password": pw})
    assert r.status_code == 302, f"login failed for {email}"
    return c


def status(trip_id):
    with fleet.app.app_context():
        return fleet.q("SELECT status FROM trips WHERE id=?", (trip_id,), one=True)[
            "status"
        ]


admin = client("admin@fleet.com", "admin123")
disp = client("dispatcher@fleet.com", "dispatch123")
drv = client("driver1@fleet.com", "driver123")
cust = client("customer@fleet.com", "customer123")

assert (
    fleet.app.test_client()
    .post("/login", data={"email": "admin@fleet.com", "password": "x"})
    .status_code
    == 200
)
assert fleet.app.test_client().get("/dashboard").status_code == 302  # login required
assert drv.get("/dashboard").status_code == 403  # role check
assert cust.get("/tractors").status_code == 403

# 1. Onboard + approve a new tractor
r = admin.post(
    "/tractors/new",
    data=dict(
        reg_no="ap37zz9999",
        make="Tata",
        model="X",
        chassis_no="c",
        engine_no="e",
        capacity_tons="20",
        gps_device_id="G9",
    ),
)
tid = int(r.headers["Location"].rstrip("/").split("/")[-1])
admin.post(f"/tractors/{tid}/approve")  # no docs -> must refuse
with fleet.app.app_context():
    assert (
        fleet.q("SELECT status FROM tractors WHERE id=?", (tid,), one=True)["status"]
        == "Pending"
    )
admin.post(
    f"/tractors/{tid}/docs",
    data=dict(doc_type="RC", doc_number="1", expiry_date="2099-01-01"),
)
admin.post(f"/tractors/{tid}/approve")
with fleet.app.app_context():
    assert (
        fleet.q("SELECT status FROM tractors WHERE id=?", (tid,), one=True)["status"]
        == "Available"
    )

# 2. Customer creates an order (seed order #1 already exists, new one is #2)
cust.post(
    "/orders/new",
    data=dict(
        pickup_location="Yard",
        pickup_lat="16.5062",
        pickup_lng="80.6480",
        drop_location="Site",
        drop_lat="16.7107",
        drop_lng="81.0952",
        material="Sand",
        quantity="10",
        unit="tons",
    ),
)

# 3. Dispatcher assigns order 2
assert "Assign order #2" in disp.get("/orders/2/assign").get_data(as_text=True)
r = disp.post("/orders/2/assign", data=dict(tractor_id=str(tid), driver_id="1"))
trip = int(r.headers["Location"].rstrip("/").split("/")[-1])
assert status(trip) == "Assigned"

# 4. Loading
disp.post(f"/trips/{trip}/action/start_loading")
disp.post(
    f"/trips/{trip}/action/finish_loading",
    data=dict(loaded_qty="10", weight_kg="10020", seal_no="S-77"),
)
assert status(trip) == "Loaded"

# Driver cannot do dispatcher actions; other driver cannot open this trip
assert (
    drv.post(f"/trips/{trip}/action/close").status_code == 302
    and status(trip) == "Loaded"
)
other = client("driver2@fleet.com", "driver123")
assert other.get(f"/trips/{trip}").status_code == 403

# 5. Transit + GPS + geofence
drv.post(f"/trips/{trip}/action/start_transit")
assert status(trip) == "In Transit"
r = drv.post(f"/api/trips/{trip}/location", json=dict(lat=16.60, lng=80.80, speed=40))
assert r.get_json()["auto_arrived"] is False
assert len(cust.get(f"/api/trips/{trip}/locations").get_json()["points"]) == 1
r = drv.post(f"/api/trips/{trip}/location", json=dict(lat=16.7107, lng=81.0952))
assert r.get_json()["auto_arrived"] is True and status(trip) == "Arrived"

# 6. Unloading with OTP
drv.post(f"/trips/{trip}/action/start_unloading")
page = cust.get(f"/trips/{trip}").get_data(as_text=True)
otp = re.search(r'class="otp">(\d{4})<', page).group(1)
assert 'class="otp"' not in drv.get(f"/trips/{trip}").get_data(
    as_text=True
)  # driver must not see OTP
drv.post(
    f"/trips/{trip}/action/confirm_delivery",
    data=dict(
        otp="0000" if otp != "0000" else "1111", received_qty="10", receiver_name="Anil"
    ),
)
assert status(trip) == "Unloading"  # wrong OTP rejected
drv.post(
    f"/trips/{trip}/action/confirm_delivery",
    data=dict(otp=otp, received_qty="9.8", receiver_name="Anil"),
)
assert status(trip) == "Delivered"

# 7. Close -> tractor and driver free again
admin.post(f"/trips/{trip}/action/close")
assert status(trip) == "Closed"
with fleet.app.app_context():
    assert (
        fleet.q("SELECT status FROM tractors WHERE id=?", (tid,), one=True)["status"]
        == "Available"
    )
    assert (
        fleet.q("SELECT status FROM drivers WHERE id=1", one=True)["status"]
        == "Available"
    )
    assert (
        fleet.q(
            "SELECT COUNT(*) c FROM trip_status_log WHERE trip_id=?", (trip,), one=True
        )["c"]
        == 8
    )

# 8. Every page renders for every role
for c, urls in [
    (
        admin,
        [
            "/dashboard",
            "/tractors",
            f"/tractors/{tid}",
            "/drivers",
            "/customers",
            "/orders",
            "/trips",
            "/trips/%d" % trip,
            "/tractors/new",
            "/drivers/new",
            "/customers/new",
            "/orders/new",
        ],
    ),
    (drv, ["/driver", f"/trips/{trip}"]),
    (cust, ["/customer", f"/trips/{trip}", "/orders/new"]),
]:
    for u in urls:
        assert c.get(u).status_code == 200, u
print("ALL TESTS PASSED")
