"""
test_endpoints.py

Shows the two strategies for testing protected endpoints:
  - Approach A: log in for a REAL token (tests auth itself)
  - Approach B: OVERRIDE the auth dependency (tests everything behind auth)
Plus RBAC branches and a MOCKED external service.
"""

from main import User, app, get_current_user, get_notifier


# ===========================================================================
# APPROACH A - use a real token (integration-style, tests the auth flow)
# ===========================================================================
def test_login_returns_a_token(client):
    r = client.post("/login", data={"username": "alice", "password": "password123"})
    assert r.status_code == 200
    assert r.json()["access_token"] == "alice"


def test_login_wrong_password_returns_401(client):
    # Login is form data -> use data=, not json=
    r = client.post("/login", data={"username": "alice", "password": "nope"})
    assert r.status_code == 401


def test_me_with_real_token(client):
    token = client.post(
        "/login", data={"username": "alice", "password": "password123"}
    ).json()["access_token"]
    r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "alice"


def test_protected_route_without_token_returns_401(client):
    # No override, no token -> the real dependency rejects it.
    assert client.get("/me").status_code == 401


# ===========================================================================
# APPROACH B - override get_current_user (unit-style, no login needed)
# ===========================================================================
def test_me_with_overridden_user(client):
    fake = User(id=99, username="tester", role="member")
    app.dependency_overrides[get_current_user] = lambda: fake

    r = client.get("/me")            # no token required now
    assert r.status_code == 200
    assert r.json()["username"] == "tester"


# ===========================================================================
# RBAC branches - override the current user's role
# ===========================================================================
def test_admin_route_forbidden_for_member(client):
    app.dependency_overrides[get_current_user] = lambda: User(1, "alice", "member")
    assert client.get("/admin/stats").status_code == 403


def test_admin_route_ok_for_admin(client):
    app.dependency_overrides[get_current_user] = lambda: User(2, "root", "admin")
    r = client.get("/admin/stats")
    assert r.status_code == 200
    assert r.json()["requested_by"] == "root"


def test_disabled_user_is_rejected_via_real_token(client):
    token = client.post(
        "/login", data={"username": "banned", "password": "password123"}
    ).json()["access_token"]
    r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403  # disabled users are blocked by get_current_user


# ===========================================================================
# MOCKING an external service with a fake, then asserting how it was used
# ===========================================================================
class FakeNotifier:
    def __init__(self):
        self.sent = []

    def send(self, to, message):
        self.sent.append((to, message))


def test_notify_calls_the_service(client):
    fake = FakeNotifier()
    app.dependency_overrides[get_current_user] = lambda: User(1, "alice", "member")
    app.dependency_overrides[get_notifier] = lambda: fake

    r = client.post("/notify", json={"to": "bob@example.com", "message": "hi"})
    assert r.status_code == 202
    # The endpoint attempted to notify - asserted WITHOUT sending anything real.
    assert fake.sent == [("bob@example.com", "hi")]


def test_notify_not_called_on_invalid_body(client):
    fake = FakeNotifier()
    app.dependency_overrides[get_current_user] = lambda: User(1, "alice", "member")
    app.dependency_overrides[get_notifier] = lambda: fake

    r = client.post("/notify", json={"to": "bob@example.com"})  # missing 'message'
    assert r.status_code == 422
    assert fake.sent == []  # validation failed before the notifier was touched
