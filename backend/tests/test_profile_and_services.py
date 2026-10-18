"""Profile photo, richer /auth/me, and the all-cases services overview."""

import struct
import zlib
from datetime import date, datetime, timezone
from decimal import Decimal

from app.models.audit_log import AuditLog
from app.models.case_service import CaseService
from app.models.funeral_case import FuneralCase


def png_bytes(size=2):
    def chunk(tag, data):
        body = tag + data
        return (
            struct.pack(">I", len(data)) + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    raw = b"".join(b"\x00" + b"\xff\x00\x00" * size for _ in range(size))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def put_avatar(client, headers, content, name="me.png", ctype="image/png"):
    return client.post(
        "/users/me/avatar", headers=headers,
        files={"file": (name, content, ctype)},
    )


# ---- /auth/me -----------------------------------------------------------

def test_me_includes_profile_details(client, test_data, auth_headers):
    body = client.get(
        "/auth/me", headers=auth_headers(test_data["manager"])
    ).json()
    assert body["business_name"]
    assert body["member_since"]
    assert body["avatar_updated_at"] is None


# ---- avatar -------------------------------------------------------------

def test_upload_serve_and_remove_photo(client, db, test_data, auth_headers):
    user = test_data["manager"]
    h = auth_headers(user)

    r = put_avatar(client, h, png_bytes())
    assert r.status_code == 200, r.text

    me = client.get("/auth/me", headers=h).json()
    assert me["avatar_updated_at"] is not None

    got = client.get(f"/users/{user.id}/avatar", headers=h)
    assert got.status_code == 200
    assert got.headers["content-type"] == "image/png"
    assert got.content.startswith(b"\x89PNG")

    assert client.delete("/users/me/avatar", headers=h).status_code == 204
    assert client.get(f"/users/{user.id}/avatar", headers=h).status_code == 404
    assert client.get("/auth/me", headers=h).json()["avatar_updated_at"] is None


def test_replacing_photo_keeps_one_file(client, test_data, auth_headers):
    from app.services import avatar_storage

    user = test_data["staff"]
    h = auth_headers(user)
    put_avatar(client, h, png_bytes())
    put_avatar(client, h, b"\xff\xd8\xff\xe0" + b"0" * 50, "x.jpg", "image/jpeg")

    found = avatar_storage.find_avatar(user.business_id, user.id)
    assert found and found[0].suffix == ".jpg"
    assert not (
        avatar_storage.STORAGE_ROOT / str(user.business_id) / f"{user.id}.png"
    ).exists()
    client.delete("/users/me/avatar", headers=h)


def test_rejects_non_images_and_big_files(client, test_data, auth_headers):
    h = auth_headers(test_data["staff"])

    # A script renamed to .png with an image content type is still refused.
    bad = put_avatar(client, h, b"<script>alert(1)</script>", "a.png", "image/png")
    assert bad.status_code == 400

    big = put_avatar(client, h, b"\x89PNG\r\n\x1a\n" + b"0" * (2 * 1024 * 1024 + 1))
    assert big.status_code == 400 and "2 MB" in big.json()["detail"]

    assert put_avatar(client, h, b"").status_code == 400


def test_colleague_can_see_photo_other_business_cannot(
    client, test_data, auth_headers
):
    owner = test_data["manager"]
    put_avatar(client, auth_headers(owner), png_bytes())

    same = client.get(
        f"/users/{owner.id}/avatar",
        headers=auth_headers(test_data["staff"]),
    )
    assert same.status_code == 200

    other = client.get(
        f"/users/{owner.id}/avatar",
        headers=auth_headers(test_data["other_business_manager"]),
    )
    assert other.status_code == 404

    client.delete("/users/me/avatar", headers=auth_headers(owner))


def test_photo_change_is_audited_without_the_picture(
    client, db, test_data, auth_headers
):
    user = test_data["staff"]
    h = auth_headers(user)
    put_avatar(client, h, png_bytes())
    client.delete("/users/me/avatar", headers=h)

    logs = db.query(AuditLog).filter_by(action="user.avatar_changed").all()
    assert [l.details["removed"] for l in logs] == [False, True]


def test_photo_requires_sign_in(client):
    assert client.post(
        "/users/me/avatar", files={"file": ("a.png", png_bytes(), "image/png")}
    ).status_code in (401, 403)


# ---- services overview --------------------------------------------------

def make_case(db, business, number, name="Test Person", archived=False):
    case = FuneralCase(
        business_id=business.id, case_number=number,
        deceased_full_name=name, status="open", is_archived=archived,
    )
    db.add(case)
    db.commit()
    return case


def make_service(db, business, case, name, when=None, status="pending",
                 kind="service"):
    service = CaseService(
        business_id=business.id, case_id=case.id, service_type=kind,
        service_name=name, status=status, quantity=1,
        unit_price=Decimal("10"), total_price=Decimal("10"),
        scheduled_date=when, provider="Prov",
    )
    db.add(service)
    db.commit()
    return service


def test_overview_lists_across_cases_soonest_first(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    c1 = make_case(db, biz, "C1", "Alpha One")
    c2 = make_case(db, biz, "C2", "Beta Two")
    make_service(db, biz, c1, "Later", datetime(2026, 12, 1, tzinfo=timezone.utc))
    make_service(db, biz, c2, "Sooner", datetime(2026, 11, 1, tzinfo=timezone.utc))
    make_service(db, biz, c2, "Unscheduled")

    body = client.get(
        "/services", headers=auth_headers(test_data["staff"])
    ).json()
    assert body["total"] == 3
    names = [i["service_name"] for i in body["items"]]
    assert names == ["Sooner", "Later", "Unscheduled"]
    assert body["items"][0]["case_number"] == "C2"


def test_overview_filters_and_search(client, db, test_data, auth_headers):
    biz = test_data["business_a"]
    c1 = make_case(db, biz, "C1", "Alpha One")
    c2 = make_case(db, biz, "C2", "Beta Two")
    make_service(db, biz, c1, "Hearse hire", status="confirmed", kind="transport")
    make_service(db, biz, c2, "Flowers")
    h = auth_headers(test_data["staff"])

    def ids(**params):
        return {
            i["service_name"]
            for i in client.get("/services", headers=h, params=params).json()["items"]
        }

    assert ids(status="confirmed") == {"Hearse hire"}
    assert ids(service_type="transport") == {"Hearse hire"}
    assert ids(q="beta") == {"Flowers"}
    assert ids(q="hearse") == {"Hearse hire"}
    assert ids(q="nothing-matches") == set()


def test_overview_hides_archived_cases_and_other_businesses(
    client, db, test_data, auth_headers
):
    a, b = test_data["business_a"], test_data["business_b"]
    live = make_case(db, a, "C1")
    gone = make_case(db, a, "C2", archived=True)
    foreign = make_case(db, b, "X1")
    make_service(db, a, live, "Mine")
    make_service(db, a, gone, "Archived")
    make_service(db, b, foreign, "Theirs")
    h = auth_headers(test_data["staff"])

    names = {i["service_name"] for i in client.get("/services", headers=h).json()["items"]}
    assert names == {"Mine"}

    withall = {
        i["service_name"]
        for i in client.get("/services", headers=h, params={"include_archived": True}).json()["items"]
    }
    assert withall == {"Mine", "Archived"}


def test_overview_paging_and_options(client, db, test_data, auth_headers):
    biz = test_data["business_a"]
    c = make_case(db, biz, "C1")
    for n in range(5):
        make_service(db, biz, c, f"S{n}", kind="flowers" if n else "transport")
    h = auth_headers(test_data["staff"])

    page = client.get("/services", headers=h, params={"limit": 2, "offset": 4}).json()
    assert page["total"] == 5 and len(page["items"]) == 1

    opts = client.get("/services/options", headers=h).json()
    assert opts["types"] == ["flowers", "transport"]
    assert opts["statuses"] == ["pending"]
    assert client.get("/services", headers=h, params={"limit": 999}).status_code == 422


def test_overview_needs_sign_in(client):
    assert client.get("/services").status_code in (401, 403)
