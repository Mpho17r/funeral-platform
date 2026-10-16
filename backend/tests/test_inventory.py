import uuid

from datetime import date
from decimal import Decimal

from sqlalchemy import func

from app.models.audit_log import AuditLog
from app.models.branch import Branch
from app.models.funeral_case import FuneralCase
from app.models.inventory import InventoryItem, StockMovement, Supplier
from app.models.permission import Permission
from app.models.user_permission import UserPermission


# ============================================================
# HELPERS
# ============================================================

def set_permission(db, user_id, key, effect):
    permission = (
        db.query(Permission).filter(Permission.key == key).first()
    )
    assert permission is not None

    db.add(
        UserPermission(
            user_id=user_id,
            permission_id=permission.id,
            effect=effect,
        )
    )
    db.commit()


def make_branch(db, business, name="Main", code="MAIN", *, main=False,
                active=True):
    branch = Branch(
        business_id=business.id,
        name=name,
        code=code,
        is_main=main,
        is_active=active,
    )
    db.add(branch)
    db.commit()

    return branch


def make_case(db, business, *, archived=False):
    case = FuneralCase(
        business_id=business.id,
        case_number=f"INV-{uuid.uuid4().hex[:8].upper()}",
        deceased_full_name="Private Name",
        date_of_death=date(2026, 10, 1),
        status="open",
        is_archived=archived,
    )
    db.add(case)
    db.commit()

    return case


def audits(db, entity_id, action=None):
    query = db.query(AuditLog).filter(AuditLog.entity_id == entity_id)

    if action:
        query = query.filter(AuditLog.action == action)

    return query.all()


def post_supplier(client, headers, name="Acme Coffins", **extra):
    return client.post(
        "/suppliers", json={"name": name, **extra}, headers=headers
    )


def post_item(client, headers, sku="cof-001", name="Pine Coffin",
              category="coffin", **extra):
    return client.post(
        "/inventory/items",
        json={"sku": sku, "name": name, "category": category, **extra},
        headers=headers,
    )


def make_item(client, headers, **extra):
    response = post_item(client, headers, **extra)
    assert response.status_code == 201, response.text

    return response.json()


def move(client, headers, item_id, movement_type, quantity, **extra):
    return client.post(
        f"/inventory/items/{item_id}/movements",
        json={
            "movement_type": movement_type,
            "quantity": str(quantity),
            **extra,
        },
        headers=headers,
    )


def stock_of(client, headers, item_id):
    response = client.get(
        f"/inventory/items/{item_id}", headers=headers
    )
    assert response.status_code == 200, response.text

    return Decimal(response.json()["quantity_on_hand"])


# ============================================================
# SUPPLIERS
# ============================================================

def test_supplier_is_created_with_audit(
    client, db, test_data, auth_headers,
):
    admin = test_data["main_admin"]

    response = post_supplier(
        client, auth_headers(admin), name="  Acme Coffins ",
        phone="0115550000",
    )

    assert response.status_code == 201, response.text

    supplier = response.json()

    assert supplier["name"] == "Acme Coffins"
    assert supplier["is_active"] is True

    entries = audits(db, uuid.UUID(supplier["id"]), "supplier.created")

    assert len(entries) == 1
    assert entries[0].user_id == admin.id
    assert entries[0].business_id == test_data["business_a"].id


def test_supplier_names_are_unique_per_business_ignoring_case(
    client, test_data, auth_headers,
):
    admin = auth_headers(test_data["main_admin"])
    other = auth_headers(test_data["other_business_manager"])

    assert post_supplier(client, admin).status_code == 201

    duplicate = post_supplier(client, admin, name="acme COFFINS")

    assert duplicate.status_code == 409
    assert "already exists" in duplicate.json()["detail"]

    # Another business may use the same name.
    assert post_supplier(client, other).status_code == 201


def test_blank_supplier_name_is_rejected(
    client, test_data, auth_headers,
):
    response = post_supplier(
        client, auth_headers(test_data["main_admin"]), name="   "
    )

    assert response.status_code == 422


def test_suppliers_list_hides_inactive_and_searches(
    client, test_data, auth_headers,
):
    admin = auth_headers(test_data["main_admin"])

    keep = post_supplier(client, admin, name="Flowers R Us").json()
    gone = post_supplier(client, admin, name="Old Caskets").json()

    client.post(f"/suppliers/{gone['id']}/deactivate", headers=admin)

    names = [
        s["name"] for s in client.get("/suppliers", headers=admin).json()
    ]
    assert names == ["Flowers R Us"]

    everything = client.get(
        "/suppliers", params={"include_inactive": True}, headers=admin
    ).json()
    assert {s["name"] for s in everything} == {
        "Flowers R Us", "Old Caskets",
    }

    found = client.get(
        "/suppliers", params={"search": "flowers"}, headers=admin
    ).json()
    assert [s["id"] for s in found] == [keep["id"]]


def test_supplier_update_is_audited_without_personal_values(
    client, db, test_data, auth_headers,
):
    admin = auth_headers(test_data["main_admin"])

    supplier = post_supplier(
        client, admin, phone="0115550000", contact_person="Sam"
    ).json()

    response = client.patch(
        f"/suppliers/{supplier['id']}",
        json={"phone": "0829998888", "contact_person": "Pat"},
        headers=admin,
    )

    assert response.status_code == 200, response.text
    assert response.json()["phone"] == "0829998888"

    entries = audits(db, uuid.UUID(supplier["id"]), "supplier.updated")

    assert len(entries) == 1
    assert "0829998888" not in str(entries[0].details)
    assert "0115550000" not in str(entries[0].details)
    assert "phone" in str(entries[0].details)


def test_supplier_update_rejects_null_name_and_unknown_fields(
    client, test_data, auth_headers,
):
    admin = auth_headers(test_data["main_admin"])
    supplier = post_supplier(client, admin).json()

    assert client.patch(
        f"/suppliers/{supplier['id']}", json={"name": None},
        headers=admin,
    ).status_code == 422

    assert client.patch(
        f"/suppliers/{supplier['id']}", json={"is_active": False},
        headers=admin,
    ).status_code == 422


def test_supplier_rename_cannot_collide(
    client, test_data, auth_headers,
):
    admin = auth_headers(test_data["main_admin"])

    post_supplier(client, admin, name="One")
    two = post_supplier(client, admin, name="Two").json()

    response = client.patch(
        f"/suppliers/{two['id']}", json={"name": "ONE"}, headers=admin
    )

    assert response.status_code == 409


def test_supplier_deactivate_and_reactivate_rules(
    client, db, test_data, auth_headers,
):
    admin = auth_headers(test_data["main_admin"])
    supplier = post_supplier(client, admin).json()
    sid = supplier["id"]

    assert client.post(
        f"/suppliers/{sid}/reactivate", headers=admin
    ).status_code == 409

    assert client.post(
        f"/suppliers/{sid}/deactivate", headers=admin
    ).status_code == 200
    assert client.post(
        f"/suppliers/{sid}/deactivate", headers=admin
    ).status_code == 409

    assert client.post(
        f"/suppliers/{sid}/reactivate", headers=admin
    ).status_code == 200

    assert audits(db, uuid.UUID(sid), "supplier.deactivated")
    assert audits(db, uuid.UUID(sid), "supplier.reactivated")


def test_supplier_permissions(client, db, test_data, auth_headers):
    admin = auth_headers(test_data["main_admin"])
    staff = auth_headers(test_data["staff"])
    supplier = post_supplier(client, admin).json()

    assert client.get("/suppliers", headers=staff).status_code == 200
    assert post_supplier(
        client, staff, name="Nope"
    ).status_code == 403
    assert client.patch(
        f"/suppliers/{supplier['id']}", json={"name": "X"},
        headers=staff,
    ).status_code == 403
    assert client.post(
        f"/suppliers/{supplier['id']}/deactivate", headers=staff
    ).status_code == 403

    set_permission(db, test_data["staff"].id, "suppliers.view", "deny")

    assert client.get("/suppliers", headers=staff).status_code == 403


def test_suppliers_are_tenant_isolated(client, test_data, auth_headers):
    admin = auth_headers(test_data["main_admin"])
    other = auth_headers(test_data["other_business_manager"])

    supplier = post_supplier(client, admin).json()
    sid = supplier["id"]

    assert client.get(f"/suppliers/{sid}", headers=other).status_code == 404
    assert client.patch(
        f"/suppliers/{sid}", json={"name": "Hijack"}, headers=other
    ).status_code == 404
    assert client.post(
        f"/suppliers/{sid}/deactivate", headers=other
    ).status_code == 404
    assert client.get("/suppliers", headers=other).json() == []


# ============================================================
# ITEMS
# ============================================================

def test_item_is_created_with_clean_sku_and_audit(
    client, db, test_data, auth_headers,
):
    admin = test_data["main_admin"]

    response = post_item(
        client, auth_headers(admin), sku=" cof-001 ", name=" Pine ",
        reorder_level="2", unit_cost="1500.50",
    )

    assert response.status_code == 201, response.text

    item = response.json()

    assert item["sku"] == "COF-001"
    assert item["name"] == "Pine"
    assert item["unit"] == "each"
    assert Decimal(item["quantity_on_hand"]) == 0
    assert Decimal(item["unit_cost"]) == Decimal("1500.50")
    # Nothing on the shelf yet, against a reorder level of 2.
    assert item["is_low_stock"] is True

    entries = audits(db, uuid.UUID(item["id"]), "inventory_item.created")

    assert len(entries) == 1
    assert entries[0].user_id == admin.id
    assert entries[0].details["sku"] == "COF-001"


def test_opening_quantity_is_recorded_as_a_receipt(
    client, db, test_data, auth_headers,
):
    admin = auth_headers(test_data["main_admin"])

    item = make_item(client, admin, opening_quantity="5")

    assert Decimal(item["quantity_on_hand"]) == 5

    movements = client.get(
        f"/inventory/items/{item['id']}/movements", headers=admin
    ).json()

    assert len(movements) == 1
    assert movements[0]["movement_type"] == "receipt"
    assert Decimal(movements[0]["quantity"]) == 5
    assert Decimal(movements[0]["balance_after"]) == 5
    assert movements[0]["reason"] == "Opening stock"


def test_sku_is_unique_per_business(client, test_data, auth_headers):
    admin = auth_headers(test_data["main_admin"])
    other = auth_headers(test_data["other_business_manager"])

    make_item(client, admin, sku="A1")

    duplicate = post_item(client, admin, sku="a1", name="Other")

    assert duplicate.status_code == 409
    assert "SKU" in duplicate.json()["detail"]

    assert post_item(client, other, sku="A1").status_code == 201


def test_invalid_item_input_is_rejected(client, test_data, auth_headers):
    admin = auth_headers(test_data["main_admin"])

    assert post_item(client, admin, category="weapons").status_code == 422
    assert post_item(client, admin, sku="has space").status_code == 422
    assert post_item(client, admin, sku="  ").status_code == 422
    assert post_item(
        client, admin, reorder_level="-1"
    ).status_code == 422
    assert post_item(
        client, admin, opening_quantity="-3"
    ).status_code == 422
    assert post_item(
        client, admin, unit_cost="-1"
    ).status_code == 422


def test_item_supplier_must_be_active_and_in_this_business(
    client, test_data, auth_headers,
):
    admin = auth_headers(test_data["main_admin"])
    other = auth_headers(test_data["other_business_manager"])

    active = post_supplier(client, admin, name="Active").json()
    inactive = post_supplier(client, admin, name="Inactive").json()
    client.post(f"/suppliers/{inactive['id']}/deactivate", headers=admin)
    foreign = post_supplier(client, other, name="Foreign").json()

    ok = post_item(
        client, admin, sku="S1", supplier_id=active["id"]
    )
    assert ok.status_code == 201
    assert ok.json()["supplier_id"] == active["id"]

    assert post_item(
        client, admin, sku="S2", supplier_id=inactive["id"]
    ).status_code == 409
    assert post_item(
        client, admin, sku="S3", supplier_id=foreign["id"]
    ).status_code == 422
    assert post_item(
        client, admin, sku="S4", supplier_id=str(uuid.uuid4())
    ).status_code == 422


def test_new_items_go_to_the_creators_branch_then_main(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    main = make_branch(db, business, "Main", "MAIN", main=True)
    soweto = make_branch(db, business, "Soweto", "SWT")
    admin = auth_headers(test_data["main_admin"])

    assert make_item(client, admin, sku="B1")["branch_id"] == str(main.id)

    test_data["main_admin"].branch_id = soweto.id
    db.commit()

    assert make_item(client, admin, sku="B2")["branch_id"] == str(
        soweto.id
    )

    explicit = make_item(
        client, admin, sku="B3", branch_id=str(main.id)
    )
    assert explicit["branch_id"] == str(main.id)

    inactive = make_branch(db, business, "Old", "OLD", active=False)
    assert post_item(
        client, admin, sku="B4", branch_id=str(inactive.id)
    ).status_code == 409
    assert post_item(
        client, admin, sku="B5", branch_id=str(uuid.uuid4())
    ).status_code == 422


def test_item_update_is_audited_and_protects_stock_fields(
    client, db, test_data, auth_headers,
):
    admin = auth_headers(test_data["main_admin"])
    item = make_item(client, admin, opening_quantity="4")

    response = client.patch(
        f"/inventory/items/{item['id']}",
        json={"name": "Oak Coffin", "reorder_level": "3",
              "category": "casket"},
        headers=admin,
    )

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Oak Coffin"
    assert response.json()["is_low_stock"] is False

    entries = audits(db, uuid.UUID(item["id"]), "inventory_item.updated")

    assert len(entries) == 1
    assert "reorder_level" in str(entries[0].details)

    # Stock, SKU and branch can only change by the proper routes.
    for field, value in (
        ("quantity_on_hand", "99"),
        ("sku", "NEW"),
        ("branch_id", str(uuid.uuid4())),
        ("is_active", False),
    ):
        assert client.patch(
            f"/inventory/items/{item['id']}",
            json={field: value},
            headers=admin,
        ).status_code == 422

    assert client.patch(
        f"/inventory/items/{item['id']}", json={"name": None},
        headers=admin,
    ).status_code == 422

    assert stock_of(client, admin, item["id"]) == 4


def test_low_stock_flag_and_filter(client, test_data, auth_headers):
    admin = auth_headers(test_data["main_admin"])

    low = make_item(
        client, admin, sku="LOW", opening_quantity="2",
        reorder_level="2",
    )
    fine = make_item(
        client, admin, sku="FINE", opening_quantity="3",
        reorder_level="2",
    )
    untracked = make_item(client, admin, sku="NONE")

    assert low["is_low_stock"] is True
    assert fine["is_low_stock"] is False
    # No reorder level set, so it never counts as low.
    assert untracked["is_low_stock"] is False

    flagged = client.get(
        "/inventory/items", params={"low_stock": True}, headers=admin
    ).json()

    assert [i["sku"] for i in flagged] == ["LOW"]

    # Using stock tips the other item over.
    move(client, admin, fine["id"], "issue", 1)

    flagged = client.get(
        "/inventory/items", params={"low_stock": True}, headers=admin
    ).json()

    assert {i["sku"] for i in flagged} == {"LOW", "FINE"}


def test_item_list_filters(client, db, test_data, auth_headers):
    business = test_data["business_a"]
    main = make_branch(db, business, "Main", "MAIN", main=True)
    soweto = make_branch(db, business, "Soweto", "SWT")
    admin = auth_headers(test_data["main_admin"])

    supplier = post_supplier(client, admin).json()

    make_item(client, admin, sku="C1", name="Pine Coffin",
              category="coffin", branch_id=str(main.id),
              supplier_id=supplier["id"])
    make_item(client, admin, sku="F1", name="Lily Wreath",
              category="flowers", branch_id=str(soweto.id))
    gone = make_item(client, admin, sku="X1", name="Retired",
                     category="other")
    client.post(f"/inventory/items/{gone['id']}/deactivate", headers=admin)

    def skus(**params):
        return sorted(
            i["sku"] for i in client.get(
                "/inventory/items", params=params, headers=admin
            ).json()
        )

    assert skus() == ["C1", "F1"]
    assert skus(include_inactive=True) == ["C1", "F1", "X1"]
    assert skus(category="flowers") == ["F1"]
    assert skus(branch_id=str(soweto.id)) == ["F1"]
    assert skus(supplier_id=supplier["id"]) == ["C1"]
    assert skus(search="wreath") == ["F1"]
    assert skus(search="c1") == ["C1"]
    assert client.get(
        "/inventory/items", params={"category": "bogus"}, headers=admin
    ).status_code == 422


def test_item_deactivate_and_reactivate(client, db, test_data, auth_headers):
    admin = auth_headers(test_data["main_admin"])
    item = make_item(client, admin, opening_quantity="2")
    iid = item["id"]

    assert client.post(
        f"/inventory/items/{iid}/reactivate", headers=admin
    ).status_code == 409

    assert client.post(
        f"/inventory/items/{iid}/deactivate", headers=admin
    ).status_code == 200
    assert client.post(
        f"/inventory/items/{iid}/deactivate", headers=admin
    ).status_code == 409

    # An inactive item cannot take stock movements.
    blocked = move(client, admin, iid, "receipt", 1)
    assert blocked.status_code == 409
    assert "inactive" in blocked.json()["detail"]

    assert client.post(
        f"/inventory/items/{iid}/reactivate", headers=admin
    ).status_code == 200
    assert move(client, admin, iid, "receipt", 1).status_code == 201

    assert audits(db, uuid.UUID(iid), "inventory_item.deactivated")
    assert audits(db, uuid.UUID(iid), "inventory_item.reactivated")


def test_item_permissions(client, db, test_data, auth_headers):
    admin = auth_headers(test_data["main_admin"])
    staff = auth_headers(test_data["staff"])
    manager = auth_headers(test_data["manager"])

    item = make_item(client, admin)

    # Staff can look but not create or edit.
    assert client.get("/inventory/items", headers=staff).status_code == 200
    assert post_item(client, staff, sku="NOPE").status_code == 403
    assert client.patch(
        f"/inventory/items/{item['id']}", json={"name": "X"},
        headers=staff,
    ).status_code == 403
    assert client.post(
        f"/inventory/items/{item['id']}/deactivate", headers=staff
    ).status_code == 403

    # Managers can manage.
    assert post_item(client, manager, sku="MGR").status_code == 201

    set_permission(db, test_data["staff"].id, "inventory.view", "deny")

    assert client.get("/inventory/items", headers=staff).status_code == 403


def test_items_are_tenant_isolated(client, test_data, auth_headers):
    admin = auth_headers(test_data["main_admin"])
    other = auth_headers(test_data["other_business_manager"])

    item = make_item(client, admin, opening_quantity="3")
    iid = item["id"]

    assert client.get(
        f"/inventory/items/{iid}", headers=other
    ).status_code == 404
    assert client.patch(
        f"/inventory/items/{iid}", json={"name": "Hijack"}, headers=other
    ).status_code == 404
    assert move(client, other, iid, "issue", 1).status_code == 404
    assert client.post(
        f"/inventory/items/{iid}/adjustments",
        json={"quantity": "-3", "reason": "theft"}, headers=other,
    ).status_code == 404
    assert client.get(
        f"/inventory/items/{iid}/movements", headers=other
    ).status_code == 404
    assert client.get("/inventory/items", headers=other).json() == []

    assert stock_of(client, admin, iid) == 3


# ============================================================
# MOVEMENTS
# ============================================================

def test_receipt_adds_stock_and_records_cost_supplier_and_reference(
    client, db, test_data, auth_headers,
):
    admin = auth_headers(test_data["main_admin"])
    supplier = post_supplier(client, admin).json()
    item = make_item(client, admin, opening_quantity="1",
                     unit_cost="1000")

    response = move(
        client, admin, item["id"], "receipt", "4",
        unit_cost="1200", supplier_id=supplier["id"],
        reference="INV-778",
    )

    assert response.status_code == 201, response.text

    movement = response.json()

    assert movement["movement_type"] == "receipt"
    assert Decimal(movement["quantity"]) == 4
    assert Decimal(movement["balance_after"]) == 5
    assert movement["supplier_id"] == supplier["id"]
    assert movement["reference"] == "INV-778"
    assert movement["created_by"] == str(test_data["main_admin"].id)

    refreshed = client.get(
        f"/inventory/items/{item['id']}", headers=admin
    ).json()

    assert Decimal(refreshed["quantity_on_hand"]) == 5
    # The item's cost follows the latest receipt.
    assert Decimal(refreshed["unit_cost"]) == 1200

    entries = audits(
        db, uuid.UUID(item["id"]), "inventory.stock_received"
    )

    assert len(entries) == 1
    assert entries[0].details["quantity"] == "4.00"
    assert entries[0].details["balance_after"] == "5.00"


def test_staff_can_receive_issue_and_return_stock(
    client, db, test_data, auth_headers,
):
    admin = auth_headers(test_data["main_admin"])
    staff = auth_headers(test_data["staff"])
    case = make_case(db, test_data["business_a"])

    item = make_item(client, admin)

    assert move(client, staff, item["id"], "receipt", 10).status_code == 201
    assert move(
        client, staff, item["id"], "issue", 3, case_id=str(case.id)
    ).status_code == 201
    assert move(
        client, staff, item["id"], "return", 1, case_id=str(case.id)
    ).status_code == 201

    assert stock_of(client, admin, item["id"]) == 8


def test_issue_to_a_case_reduces_stock_and_is_audited(
    client, db, test_data, auth_headers,
):
    admin = auth_headers(test_data["main_admin"])
    case = make_case(db, test_data["business_a"])
    item = make_item(client, admin, opening_quantity="5")

    response = move(
        client, admin, item["id"], "issue", 2, case_id=str(case.id),
        reason="Family chose the pine model",
    )

    assert response.status_code == 201, response.text

    movement = response.json()

    assert Decimal(movement["quantity"]) == -2
    assert Decimal(movement["balance_after"]) == 3
    assert movement["case_id"] == str(case.id)
    assert stock_of(client, admin, item["id"]) == 3

    entry = audits(
        db, uuid.UUID(item["id"]), "inventory.stock_issued"
    )[0]

    assert entry.details["case_number"] == case.case_number
    assert entry.details["quantity"] == "-2.00"
    # Free-text reasons stay in the ledger, not the audit trail.
    assert "pine model" not in str(entry.details)
    assert "pine model" not in (entry.notes or "")


def test_cannot_issue_more_than_is_in_stock(
    client, db, test_data, auth_headers,
):
    admin = auth_headers(test_data["main_admin"])
    item = make_item(client, admin, opening_quantity="2")

    response = move(client, admin, item["id"], "issue", 3)

    assert response.status_code == 409
    assert "Not enough" in response.json()["detail"]

    assert stock_of(client, admin, item["id"]) == 2
    assert db.query(StockMovement).count() == 1
    assert not audits(
        db, uuid.UUID(item["id"]), "inventory.stock_issued"
    )

    # Issuing exactly what is there is fine and leaves zero.
    assert move(client, admin, item["id"], "issue", 2).status_code == 201
    assert stock_of(client, admin, item["id"]) == 0


def test_movement_input_rules(client, db, test_data, auth_headers):
    admin = auth_headers(test_data["main_admin"])
    case = make_case(db, test_data["business_a"])
    supplier = post_supplier(client, admin).json()
    item = make_item(client, admin, opening_quantity="5")
    iid = item["id"]

    assert move(client, admin, iid, "receipt", 0).status_code == 422
    assert move(client, admin, iid, "receipt", -1).status_code == 422
    assert move(client, admin, iid, "receipt", "1.234").status_code == 422
    assert move(client, admin, iid, "adjustment", 1).status_code == 422

    # Only receipts carry a supplier or a cost; receipts have no case.
    assert move(
        client, admin, iid, "issue", 1, supplier_id=supplier["id"]
    ).status_code == 422
    assert move(
        client, admin, iid, "issue", 1, unit_cost="5"
    ).status_code == 422
    assert move(
        client, admin, iid, "receipt", 1, case_id=str(case.id)
    ).status_code == 422

    assert stock_of(client, admin, iid) == 5


def test_movement_supplier_and_case_must_be_valid(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    admin = auth_headers(test_data["main_admin"])
    other = auth_headers(test_data["other_business_manager"])

    item = make_item(client, admin, opening_quantity="5")
    iid = item["id"]

    inactive = post_supplier(client, admin, name="Gone").json()
    client.post(f"/suppliers/{inactive['id']}/deactivate", headers=admin)
    foreign_supplier = post_supplier(client, other, name="Far").json()

    assert move(
        client, admin, iid, "receipt", 1, supplier_id=inactive["id"]
    ).status_code == 409
    assert move(
        client, admin, iid, "receipt", 1,
        supplier_id=foreign_supplier["id"],
    ).status_code == 422

    archived = make_case(db, business, archived=True)
    foreign_case = make_case(db, test_data["business_b"])

    assert move(
        client, admin, iid, "issue", 1, case_id=str(archived.id)
    ).status_code == 409
    assert move(
        client, admin, iid, "issue", 1, case_id=str(foreign_case.id)
    ).status_code == 422
    assert move(
        client, admin, iid, "issue", 1, case_id=str(uuid.uuid4())
    ).status_code == 422

    assert stock_of(client, admin, iid) == 5


def test_adjustment_needs_manage_permission_and_a_reason(
    client, db, test_data, auth_headers,
):
    admin = auth_headers(test_data["main_admin"])
    staff = auth_headers(test_data["staff"])
    item = make_item(client, admin, opening_quantity="10")
    path = f"/inventory/items/{item['id']}/adjustments"

    assert client.post(
        path, json={"quantity": "-1", "reason": "x"}, headers=staff
    ).status_code == 403

    assert client.post(
        path, json={"quantity": "-1"}, headers=admin
    ).status_code == 422
    assert client.post(
        path, json={"quantity": "-1", "reason": "   "}, headers=admin
    ).status_code == 422
    assert client.post(
        path, json={"quantity": "0", "reason": "nothing"}, headers=admin
    ).status_code == 422

    response = client.post(
        path,
        json={"quantity": "-2.5", "reason": "Water damage in store"},
        headers=admin,
    )

    assert response.status_code == 201, response.text
    assert Decimal(response.json()["quantity"]) == Decimal("-2.5")
    assert Decimal(response.json()["balance_after"]) == Decimal("7.5")
    assert response.json()["reason"] == "Water damage in store"

    up = client.post(
        path, json={"quantity": "1", "reason": "Recount"}, headers=admin
    )
    assert up.status_code == 201
    assert stock_of(client, admin, item["id"]) == Decimal("8.5")

    entry = audits(
        db, uuid.UUID(item["id"]), "inventory.stock_adjusted"
    )[0]
    assert "Water damage" not in str(entry.details)


def test_adjustment_cannot_take_stock_below_zero(
    client, test_data, auth_headers,
):
    admin = auth_headers(test_data["main_admin"])
    item = make_item(client, admin, opening_quantity="2")

    response = client.post(
        f"/inventory/items/{item['id']}/adjustments",
        json={"quantity": "-3", "reason": "Recount"},
        headers=admin,
    )

    assert response.status_code == 409
    assert stock_of(client, admin, item["id"]) == 2


def test_ledger_always_explains_the_quantity_on_hand(
    client, db, test_data, auth_headers,
):
    admin = auth_headers(test_data["main_admin"])
    case = make_case(db, test_data["business_a"])
    item = make_item(client, admin, opening_quantity="6")
    iid = item["id"]

    move(client, admin, iid, "receipt", "2.5")
    move(client, admin, iid, "issue", "1", case_id=str(case.id))
    move(client, admin, iid, "issue", "100")  # refused
    move(client, admin, iid, "return", "0.5", case_id=str(case.id))
    client.post(
        f"/inventory/items/{iid}/adjustments",
        json={"quantity": "-1", "reason": "Recount"}, headers=admin,
    )

    total = (
        db.query(func.sum(StockMovement.quantity))
        .filter(StockMovement.item_id == uuid.UUID(iid))
        .scalar()
    )

    assert total == Decimal("7.00")
    assert stock_of(client, admin, iid) == Decimal("7.00")

    # Each movement's balance follows on from the one before it.
    history = client.get(
        f"/inventory/items/{iid}/movements", headers=admin
    ).json()

    running = Decimal("0")
    for entry in reversed(history):
        running += Decimal(entry["quantity"])
        assert Decimal(entry["balance_after"]) == running


def test_movements_are_listed_newest_first_and_limited(
    client, test_data, auth_headers,
):
    admin = auth_headers(test_data["main_admin"])
    item = make_item(client, admin, opening_quantity="1")

    for _ in range(3):
        move(client, admin, item["id"], "receipt", 1)

    history = client.get(
        f"/inventory/items/{item['id']}/movements", headers=admin
    ).json()

    assert [Decimal(m["balance_after"]) for m in history] == [4, 3, 2, 1]

    limited = client.get(
        f"/inventory/items/{item['id']}/movements",
        params={"limit": 2}, headers=admin,
    ).json()

    assert len(limited) == 2
    assert client.get(
        f"/inventory/items/{item['id']}/movements",
        params={"limit": 0}, headers=admin,
    ).status_code == 422


def test_case_stock_lists_what_went_to_that_case(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    admin = auth_headers(test_data["main_admin"])
    staff = auth_headers(test_data["staff"])
    case = make_case(db, business)
    other_case = make_case(db, business)

    coffin = make_item(client, admin, sku="C1", opening_quantity="5")
    wreath = make_item(
        client, admin, sku="W1", category="flowers",
        opening_quantity="5",
    )

    move(client, admin, coffin["id"], "issue", 1, case_id=str(case.id))
    move(client, admin, wreath["id"], "issue", 2, case_id=str(case.id))
    move(client, admin, wreath["id"], "return", 1, case_id=str(case.id))
    move(client, admin, coffin["id"], "issue", 1,
         case_id=str(other_case.id))

    rows = client.get(f"/cases/{case.id}/stock", headers=staff).json()

    assert len(rows) == 3
    assert {r["case_id"] for r in rows} == {str(case.id)}
    assert sorted(Decimal(r["quantity"]) for r in rows) == [-2, -1, 1]

    assert client.get(
        f"/cases/{uuid.uuid4()}/stock", headers=staff
    ).status_code == 404
    assert client.get(
        f"/cases/{case.id}/stock",
        headers=auth_headers(test_data["other_business_manager"]),
    ).status_code == 404


def test_movements_need_the_stock_permission(
    client, db, test_data, auth_headers,
):
    admin = auth_headers(test_data["main_admin"])
    staff = auth_headers(test_data["staff"])
    item = make_item(client, admin, opening_quantity="3")

    set_permission(db, test_data["staff"].id, "inventory.stock", "deny")

    assert move(client, staff, item["id"], "issue", 1).status_code == 403
    assert client.get(
        f"/inventory/items/{item['id']}/movements", headers=staff
    ).status_code == 200
    assert stock_of(client, admin, item["id"]) == 3


def test_concurrent_issues_cannot_oversell(
    client, db, test_data, auth_headers,
):
    """Two issues that each fit alone but not together. The second one
    waits on the row lock, then sees the reduced stock and is refused,
    so stock can never go below zero."""

    import threading

    from app.services.inventory import (
        InventoryError,
        lock_item,
        record_movement,
    )
    from tests.conftest import TestingSessionLocal

    admin = auth_headers(test_data["main_admin"])
    business_id = test_data["business_a"].id
    item = make_item(client, admin, opening_quantity="3")
    item_id = uuid.UUID(item["id"])

    first = TestingSessionLocal()
    outcome = {}

    def second_issue():
        session = TestingSessionLocal()

        try:
            locked = lock_item(session, item_id, business_id)
            record_movement(
                session, item=locked, movement_type="issue",
                quantity=Decimal("2"), user_id=None,
            )
            session.commit()
            outcome["second"] = "issued"
        except InventoryError as error:
            session.rollback()
            outcome["second"] = error.status_code
        finally:
            session.close()

    try:
        locked = lock_item(first, item_id, business_id)
        record_movement(
            first, item=locked, movement_type="issue",
            quantity=Decimal("2"), user_id=None,
        )

        # The first issue holds the row lock, uncommitted.
        thread = threading.Thread(target=second_issue)
        thread.start()
        thread.join(timeout=1.5)

        assert thread.is_alive(), "second issue did not wait for the lock"

        first.commit()
        thread.join(timeout=10)
    finally:
        first.close()

    assert outcome == {"second": 409}
    assert stock_of(client, admin, item["id"]) == 1


# ============================================================
# BRANCH TRANSFERS
# ============================================================

def test_stock_item_can_be_moved_to_another_branch(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    main = make_branch(db, business, "Main", "MAIN", main=True)
    soweto = make_branch(db, business, "Soweto", "SWT")
    admin = auth_headers(test_data["main_admin"])
    manager = auth_headers(test_data["manager"])

    item = make_item(client, admin, opening_quantity="4")
    assert item["branch_id"] == str(main.id)

    response = client.post(
        f"/inventory/items/{item['id']}/transfer",
        json={"branch_id": str(soweto.id)},
        headers=manager,
    )

    assert response.status_code == 200, response.text
    assert response.json()["branch_id"] == str(soweto.id)
    assert Decimal(response.json()["quantity_on_hand"]) == 4

    entry = audits(
        db, uuid.UUID(item["id"]), "inventory_item.branch_changed"
    )[0]

    assert entry.details["from_branch_id"] == str(main.id)
    assert entry.details["to_branch_id"] == str(soweto.id)
    assert entry.details["sku"] == "COF-001"
    assert "Inventory item" in entry.notes

    # Already there, or an inactive target, is refused.
    assert client.post(
        f"/inventory/items/{item['id']}/transfer",
        json={"branch_id": str(soweto.id)}, headers=manager,
    ).status_code == 409

    closed = make_branch(db, business, "Closed", "CLS", active=False)
    assert client.post(
        f"/inventory/items/{item['id']}/transfer",
        json={"branch_id": str(closed.id)}, headers=manager,
    ).status_code == 409


def test_stock_transfers_need_permission_and_stay_in_the_tenant(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    make_branch(db, business, "Main", "MAIN", main=True)
    soweto = make_branch(db, business, "Soweto", "SWT")
    admin = auth_headers(test_data["main_admin"])

    item = make_item(client, admin)
    path = f"/inventory/items/{item['id']}/transfer"
    body = {"branch_id": str(soweto.id)}

    assert client.post(
        path, json=body, headers=auth_headers(test_data["staff"])
    ).status_code == 403

    other = auth_headers(test_data["other_business_manager"])
    assert client.post(path, json=body, headers=other).status_code == 404

    foreign_branch = make_branch(
        db, test_data["business_b"], "Elsewhere", "ELS", main=True
    )
    assert client.post(
        path, json={"branch_id": str(foreign_branch.id)}, headers=admin
    ).status_code == 422


# ============================================================
# DEFAULT ROLE PERMISSIONS
# ============================================================

def test_default_role_permissions_for_inventory():
    from app.services.permission_seed import DEFAULT_ROLE_PERMISSIONS

    manager = set(DEFAULT_ROLE_PERMISSIONS["manager"])
    staff = set(DEFAULT_ROLE_PERMISSIONS["staff"])

    assert {
        "inventory.view", "inventory.manage", "inventory.stock",
        "suppliers.view", "suppliers.manage",
    } <= manager

    assert {
        "inventory.view", "inventory.stock", "suppliers.view",
    } <= staff
    assert "inventory.manage" not in staff
    assert "suppliers.manage" not in staff
