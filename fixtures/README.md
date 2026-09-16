# Fixture scope

L0 establishes only a provisional scope, exposed by the backend health response:
Chicago origin; Milwaukee, Indiana Dunes, and Starved Rock destinations; USD;
one or two adults. The backend's DemoScope model is the current source for these
values. No prices, routes, or travel availability have been verified.

L2's executable catalog lives in `backend/src/travel_agent/catalog.py`, packaged
with the backend so it works independently of the current working directory.
Eight invented scenarios cover dorm/bus, fast train/hotel, camping with gear,
private-room hiking, remote lodging with expensive transfers, missing fees,
impossible timing, and overnight transport. These are not sourced offers.

Run `backend/tests/test_planning.py` for independently specified cost expectations
and ranking scenarios. Rates are uniform across dates; no seasonal availability
is implied. The API returns synthetic evidence on every cost component.
