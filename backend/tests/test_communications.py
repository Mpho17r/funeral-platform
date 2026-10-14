import uuid

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.audit_log import AuditLog
from app.models.branch import Branch
from app.models.communication import (
    CommunicationMessage,
    MemberCommunicationPreference,
    MessageTemplate,
)
from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_contribution import MembershipContribution
from app.models.membership_plan import MembershipPlan
from app.models.permission import Permission
from app.models.user_permission import UserPermission
from app.services.communications import (
    DEFAULT_TEMPLATES,
    PLACEHOLDERS,
    action_url,
    clean_email,
    days_text,
    format_date,
    format_money,
    normalize_phone,
    pick_channel,
    plan_reminders,
    render,
    today_in_south_africa,
    unknown_placeholders,
)


LAPSE_AFTER = 30


# ============================================================
# HELPERS
# ============================================================

def today():
    return today_in_south_africa()


def make_plan(db, business, *, name="Family Plan"):
    plan = MembershipPlan(
        business_id=business.id,
        name=f"{name} {uuid.uuid4().hex[:4]}",
        monthly_contribution=Decimal("250.00"),
        is_active=True,
    )
    db.add(plan)
    db.commit()

    return plan


def make_member(
    db,
    business,
    *,
    first="Thandi",
    last="Nkosi",
    phone="082 123 4567",
    email=None,
    branch=None,
    status="active",
):
    suffix = uuid.uuid4().hex[:8].upper()

    member = Member(
        business_id=business.id,
        branch_id=branch.id if branch else None,
        member_number=f"M-{suffix}",
        first_name=first,
        last_name=last,
        phone=phone,
        email=email,
        join_date=date(2025, 1, 1),
        status=status,
    )
    db.add(member)
    db.commit()

    return member


def make_membership(
    db,
    business,
    member,
    plan=None,
    *,
    status="active",
):
    plan = plan or make_plan(db, business)

    membership = Membership(
        business_id=business.id,
        member_id=member.id,
        plan_id=plan.id,
        membership_number=f"MS-{uuid.uuid4().hex[:8].upper()}",
        start_date=date(2025, 1, 1),
        status=status,
    )
    db.add(membership)
    db.commit()

    return membership


def add_contribution(
    db,
    membership,
    *,
    due,
    amount="250.00",
    paid="0.00",
    status="due",
    period=None,
):
    contribution = MembershipContribution(
        business_id=membership.business_id,
        membership_id=membership.id,
        contribution_period=period or due.replace(day=1),
        amount_due=Decimal(amount),
        amount_paid=Decimal(paid),
        due_date=due,
        status=status,
    )
    db.add(contribution)
    db.commit()

    return contribution


def setup_member(
    db,
    business,
    *,
    due,
    amount="250.00",
    paid="0.00",
    status="due",
    **member_fields,
):
    """A member with one unpaid contribution due on ``due``."""

    member = make_member(db, business, **member_fields)
    membership = make_membership(db, business, member)
    contribution = add_contribution(
        db, membership, due=due, amount=amount, paid=paid, status=status
    )

    return member, membership, contribution


def set_lapse(db, business, days=LAPSE_AFTER):
    business.lapse_after_days = days
    db.commit()


def run(db, business, **options):
    return plan_reminders(db, business, today=today(), **options)


def kinds_of(plan):
    return sorted(candidate.kind for candidate in plan.candidates)


def audits(db, action):
    return (
        db.query(AuditLog)
        .filter(AuditLog.action == action)
        .order_by(AuditLog.created_at)
        .all()
    )


def deny(db, user, key):
    permission = (
        db.query(Permission).filter(Permission.key == key).first()
    )
    assert permission is not None, key
    db.add(
        UserPermission(
            user_id=user.id,
            permission_id=permission.id,
            effect="deny",
        )
    )
    db.commit()


def call(client, auth_headers, user, method, path, **kwargs):
    return client.request(
        method, path, headers=auth_headers(user), **kwargs
    )


def generate(client, auth_headers, user, **options):
    return call(
        client,
        auth_headers,
        user,
        "POST",
        "/communications/reminders/generate",
        json=options,
    )


def preview(client, auth_headers, user, **options):
    return call(
        client,
        auth_headers,
        user,
        "POST",
        "/communications/reminders/preview",
        json=options,
    )


def messages(client, auth_headers, user, **params):
    return call(
        client,
        auth_headers,
        user,
        "GET",
        "/communications/messages",
        params=params,
    )


def queue_one(client, auth_headers, db, test_data, *, ago=5):
    """Queue a single overdue reminder and return its id."""

    business = test_data["business_a"]
    set_lapse(db, business)
    setup_member(db, business, due=today() - timedelta(days=ago))

    response = generate(
        client, auth_headers, test_data["manager"], kinds=["payment_overdue"]
    )
    assert response.status_code == 200, response.text
    assert response.json()["created"] == 1

    return db.query(CommunicationMessage).one().id


# ============================================================
# WORDING
# ============================================================

def test_render_fills_known_placeholders():
    assert (
        render("Hello {member_name}, {amount_due}", {
            "member_name": "Thandi",
            "amount_due": "R250.00",
        })
        == "Hello Thandi, R250.00"
    )


def test_render_leaves_unknown_placeholders_empty():
    assert render("Hi {nobody} there", {}) == "Hi there"


def test_render_collapses_extra_spaces():
    assert render("Call  us on {business_phone}  today", {
        "business_phone": "",
    }) == "Call us on today"


def test_unknown_placeholders_are_listed():
    assert unknown_placeholders(
        "{member_name} {oops} {amount_due} {other}"
    ) == ["oops", "other"]


def test_every_default_template_uses_only_known_placeholders():
    for kind, (subject, body) in DEFAULT_TEMPLATES.items():
        assert unknown_placeholders(subject) == [], kind
        assert unknown_placeholders(body) == [], kind


def test_money_and_dates_read_the_south_african_way():
    assert format_money(Decimal("1250")) == "R1,250.00"
    assert format_money(Decimal("0.5")) == "R0.50"
    assert format_date(date(2026, 3, 5)) == "5 March 2026"
    assert days_text(1) == "1 day"
    assert days_text(3) == "3 days"


# ============================================================
# CONTACT DETAILS
# ============================================================

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("082 123 4567", "27821234567"),
        ("0821234567", "27821234567"),
        ("082-123-4567", "27821234567"),
        ("(082) 123 4567", "27821234567"),
        ("+27 82 123 4567", "27821234567"),
        ("+27821234567", "27821234567"),
        ("27821234567", "27821234567"),
        ("0027821234567", "27821234567"),
        ("+263 77 123 4567", "263771234567"),
        ("12345", None),
        ("", None),
        (None, None),
        ("not a number", None),
        ("0821234567890123456", None),
    ],
)
def test_phone_numbers_are_normalised(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("a@b.co", "a@b.co"),
        ("  a@b.co  ", "a@b.co"),
        ("no-at-sign", None),
        ("has space@b.co", None),
        ("", None),
        (None, None),
    ],
)
def test_emails_are_cleaned(raw, expected):
    assert clean_email(raw) == expected


def test_preferred_channel_is_used_when_available(db, test_data):
    member = make_member(
        db, test_data["business_a"], phone="0821234567", email="t@x.co"
    )

    assert pick_channel(member, "email") == ("email", "t@x.co")
    assert pick_channel(member, "sms") == ("sms", "27821234567")
    assert pick_channel(member, "whatsapp") == ("whatsapp", "27821234567")


def test_channel_falls_back_when_the_preferred_one_has_no_detail(
    db, test_data
):
    no_email = make_member(
        db, test_data["business_a"], phone="0821234567", email=None
    )
    no_phone = make_member(
        db, test_data["business_a"], phone=None, email="t@x.co"
    )

    assert pick_channel(no_email, "email") == ("whatsapp", "27821234567")
    assert pick_channel(no_phone, "whatsapp") == ("email", "t@x.co")


def test_no_channel_when_there_is_no_contact_detail(db, test_data):
    member = make_member(
        db, test_data["business_a"], phone="junk", email="junk"
    )

    assert pick_channel(member, "whatsapp") is None


def make_message(channel, recipient, body="Hello & welcome?", subject=None):
    return CommunicationMessage(
        business_id=uuid.uuid4(),
        member_id=uuid.uuid4(),
        kind="custom",
        channel=channel,
        recipient=recipient,
        subject=subject,
        body=body,
        status="queued",
    )


def test_whatsapp_link_opens_the_number_with_the_text():
    url = action_url(make_message("whatsapp", "27821234567"))

    assert url.startswith("https://wa.me/27821234567?text=")
    assert "Hello%20%26%20welcome%3F" in url


def test_sms_link_carries_the_number_and_text():
    url = action_url(make_message("sms", "27821234567"))

    assert url.startswith("sms:+27821234567?body=")


def test_email_link_carries_subject_and_body():
    url = action_url(
        make_message("email", "a@b.co", subject="Due soon & more")
    )

    assert url.startswith("mailto:a@b.co?subject=Due%20soon%20%26%20more")
    assert "&body=Hello%20%26%20welcome%3F" in url


# ============================================================
# REMINDER RULES
# ============================================================

def test_due_soon_inside_the_window(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business)
    setup_member(db, business, due=today() + timedelta(days=2))

    plan = run(db, business)

    assert kinds_of(plan) == ["payment_due_soon"]


def test_due_soon_includes_today_and_the_last_day_of_the_window(
    db, test_data
):
    business = test_data["business_a"]
    set_lapse(db, business)
    setup_member(db, business, due=today())
    setup_member(db, business, due=today() + timedelta(days=3))

    assert kinds_of(run(db, business)) == [
        "payment_due_soon",
        "payment_due_soon",
    ]


def test_not_due_soon_beyond_the_window(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business)
    setup_member(db, business, due=today() + timedelta(days=4))

    assert run(db, business).candidates == []


def test_due_soon_window_can_be_changed(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business)
    setup_member(db, business, due=today() + timedelta(days=10))

    assert run(db, business).candidates == []
    assert kinds_of(run(db, business, days_before=10)) == [
        "payment_due_soon"
    ]


def test_paid_contribution_is_not_reminded(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business)
    setup_member(
        db,
        business,
        due=today() + timedelta(days=1),
        paid="250.00",
        status="paid",
    )

    assert run(db, business).candidates == []


def test_fully_paid_amount_is_not_reminded_even_if_status_is_stale(
    db, test_data
):
    business = test_data["business_a"]
    set_lapse(db, business)
    setup_member(
        db,
        business,
        due=today() - timedelta(days=5),
        paid="250.00",
        status="overdue",
    )

    assert run(db, business).candidates == []


def test_part_paid_contribution_asks_only_for_the_balance(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business)
    setup_member(
        db,
        business,
        due=today() - timedelta(days=5),
        paid="100.00",
        status="partially_paid",
    )

    plan = run(db, business, kinds=["payment_overdue"])

    assert "R150.00" in plan.candidates[0].body


def test_overdue_after_the_due_date(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business)
    setup_member(db, business, due=today() - timedelta(days=1))

    plan = run(db, business, kinds=["payment_overdue"])

    assert kinds_of(plan) == ["payment_overdue"]
    assert "1 day overdue" in plan.candidates[0].body
    assert "1 days" not in plan.candidates[0].body


def test_overdue_message_says_how_long_and_how_much(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business)
    business.name = "Mokoena Funerals"
    db.commit()

    member, membership, contribution = setup_member(
        db,
        business,
        due=today() - timedelta(days=12),
        first="Lerato",
    )

    body = run(db, business, kinds=["payment_overdue"]).candidates[0].body

    assert body.startswith("Hello Lerato,")
    assert "R250.00" in body
    assert "12 days overdue" in body
    assert membership.membership_number in body
    assert "Mokoena Funerals" in body
    assert format_date(contribution.due_date) in body


def test_not_overdue_on_the_due_date_itself(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business)
    setup_member(db, business, due=today())

    assert kinds_of(run(db, business)) == ["payment_due_soon"]


def test_oldest_unpaid_contribution_decides_the_overdue_reminder(
    db, test_data
):
    business = test_data["business_a"]
    set_lapse(db, business)

    member = make_member(db, business)
    membership = make_membership(db, business, member)
    add_contribution(
        db, membership, due=today() - timedelta(days=20),
        period=date(2020, 1, 1),
    )
    add_contribution(
        db, membership, due=today() - timedelta(days=5),
        period=date(2020, 2, 1),
    )

    plan = run(db, business, kinds=["payment_overdue"])

    assert len(plan.candidates) == 1
    assert "20 days overdue" in plan.candidates[0].body


def test_a_later_contribution_coming_due_is_reported_separately(
    db, test_data
):
    business = test_data["business_a"]
    set_lapse(db, business)

    member = make_member(db, business)
    membership = make_membership(db, business, member)
    add_contribution(
        db, membership, due=today() - timedelta(days=5),
        period=date(2020, 1, 1),
    )
    add_contribution(
        db, membership, due=today() + timedelta(days=1),
        period=date(2020, 2, 1),
    )

    assert kinds_of(run(db, business)) == [
        "payment_due_soon",
        "payment_overdue",
    ]


def test_overdue_is_not_repeated_inside_the_repeat_window(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business)
    member, membership, contribution = setup_member(
        db, business, due=today() - timedelta(days=5)
    )

    db.add(
        CommunicationMessage(
            business_id=business.id,
            member_id=member.id,
            membership_id=membership.id,
            contribution_id=contribution.id,
            kind="payment_overdue",
            channel="whatsapp",
            recipient="27821234567",
            body="Earlier reminder",
            status="sent",
            sent_at=datetime.now(timezone.utc),
            dedupe_key="payment_overdue:old",
        )
    )
    db.commit()

    assert run(db, business, kinds=["payment_overdue"]).candidates == []


def test_overdue_is_repeated_after_the_repeat_window(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business)
    member, membership, contribution = setup_member(
        db, business, due=today() - timedelta(days=15)
    )

    db.add(
        CommunicationMessage(
            business_id=business.id,
            member_id=member.id,
            membership_id=membership.id,
            contribution_id=contribution.id,
            kind="payment_overdue",
            channel="whatsapp",
            recipient="27821234567",
            body="Old reminder",
            status="sent",
            sent_at=datetime.now(timezone.utc),
            dedupe_key="payment_overdue:old",
            created_at=datetime.now(timezone.utc) - timedelta(days=8),
        )
    )
    db.commit()

    assert kinds_of(run(db, business, kinds=["payment_overdue"])) == [
        "payment_overdue"
    ]


def test_cancelled_overdue_reminder_does_not_hold_back_the_next_one(
    db, test_data
):
    business = test_data["business_a"]
    set_lapse(db, business)
    member, membership, contribution = setup_member(
        db, business, due=today() - timedelta(days=5)
    )

    db.add(
        CommunicationMessage(
            business_id=business.id,
            member_id=member.id,
            membership_id=membership.id,
            contribution_id=contribution.id,
            kind="payment_overdue",
            channel="whatsapp",
            recipient="27821234567",
            body="Cancelled one",
            status="cancelled",
            cancelled_at=datetime.now(timezone.utc),
            dedupe_key="payment_overdue:yesterday",
        )
    )
    db.commit()

    assert kinds_of(run(db, business, kinds=["payment_overdue"])) == [
        "payment_overdue"
    ]


def test_lapse_warning_inside_the_warning_window(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business, 30)
    # 25 days overdue means 5 days left.
    setup_member(db, business, due=today() - timedelta(days=25))

    plan = run(db, business, kinds=["lapse_warning"])

    assert kinds_of(plan) == ["lapse_warning"]
    assert (
        format_date(today() + timedelta(days=5)) in plan.candidates[0].body
    )


def test_no_lapse_warning_before_the_window(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business, 30)
    # 20 days overdue means 10 days left, outside the 7-day window.
    setup_member(db, business, due=today() - timedelta(days=20))

    assert run(db, business, kinds=["lapse_warning"]).candidates == []


def test_warning_window_can_be_changed(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business, 30)
    setup_member(db, business, due=today() - timedelta(days=20))

    assert kinds_of(
        run(db, business, kinds=["lapse_warning"], warning_days=10)
    ) == ["lapse_warning"]


def test_overdue_and_lapse_warning_can_both_apply(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business, 30)
    setup_member(db, business, due=today() - timedelta(days=25))

    assert kinds_of(run(db, business)) == [
        "lapse_warning",
        "payment_overdue",
    ]


def test_lapsed_notice_when_the_membership_lapsed_recently(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business, 30)
    # Lapsed 3 days ago.
    setup_member(db, business, due=today() - timedelta(days=33))

    plan = run(db, business)

    assert kinds_of(plan) == ["lapsed"]
    assert "has stopped" in plan.candidates[0].body


def test_lapsed_on_the_day_it_lapses(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business, 30)
    setup_member(db, business, due=today() - timedelta(days=30))

    assert kinds_of(run(db, business)) == ["lapsed"]


def test_no_lapsed_notice_for_old_lapses(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business, 30)
    # Lapsed 40 days ago.
    setup_member(db, business, due=today() - timedelta(days=70))

    assert run(db, business).candidates == []


def test_lapsed_notice_window_can_be_changed(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business, 30)
    setup_member(db, business, due=today() - timedelta(days=70))

    assert kinds_of(run(db, business, lapsed_notice_days=60)) == ["lapsed"]


def test_lapsed_members_get_no_overdue_or_warning(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business, 30)
    setup_member(db, business, due=today() - timedelta(days=35))

    assert kinds_of(run(db, business)) == ["lapsed"]


def test_cancelled_memberships_are_left_alone(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business)
    member = make_member(db, business)
    membership = make_membership(
        db, business, member, status="cancelled"
    )
    add_contribution(db, membership, due=today() - timedelta(days=5))

    assert run(db, business).candidates == []


def test_inactive_members_are_left_alone(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business)
    setup_member(
        db, business, due=today() - timedelta(days=5), status="inactive"
    )

    assert run(db, business).candidates == []


def test_member_with_nothing_unpaid_is_left_alone(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business)
    member = make_member(db, business)
    make_membership(db, business, member)

    assert run(db, business).candidates == []


def test_kinds_filter_limits_what_is_planned(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business, 30)
    setup_member(db, business, due=today() - timedelta(days=25))

    assert kinds_of(run(db, business, kinds=["lapse_warning"])) == [
        "lapse_warning"
    ]


def test_reminders_are_scoped_to_the_business(db, test_data):
    business = test_data["business_a"]
    other = test_data["business_b"]
    set_lapse(db, business)
    set_lapse(db, other)
    setup_member(db, other, due=today() - timedelta(days=5))

    assert run(db, business).candidates == []
    assert len(run(db, other).candidates) == 1


def test_branch_filter_limits_to_that_branch(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business)
    branch = Branch(
        business_id=business.id, name="Soweto", code="SOW", is_main=False
    )
    db.add(branch)
    db.commit()

    here, _, _ = setup_member(
        db, business, due=today() - timedelta(days=5), branch=branch
    )
    setup_member(db, business, due=today() - timedelta(days=5))

    plan = run(db, business, kinds=["payment_overdue"], branch_id=branch.id)

    assert [c.member.id for c in plan.candidates] == [here.id]


# ============================================================
# WHO IS SKIPPED, AND HOW THEY ARE REACHED
# ============================================================

def test_opted_out_members_are_skipped_and_reported(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business)
    member, membership, _ = setup_member(
        db, business, due=today() - timedelta(days=5)
    )
    db.add(
        MemberCommunicationPreference(
            member_id=member.id,
            business_id=business.id,
            preferred_channel="whatsapp",
            opted_out=True,
            opted_out_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    plan = run(db, business, kinds=["payment_overdue"])

    assert plan.candidates == []
    assert [(s.reason, s.membership_number) for s in plan.skipped] == [
        ("opted_out", membership.membership_number)
    ]


def test_members_without_contact_details_are_skipped_and_reported(
    db, test_data
):
    business = test_data["business_a"]
    set_lapse(db, business)
    setup_member(
        db, business, due=today() - timedelta(days=5), phone=None
    )

    plan = run(db, business, kinds=["payment_overdue"])

    assert plan.candidates == []
    assert [s.reason for s in plan.skipped] == ["no_contact"]


def test_preferred_channel_is_respected(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business)
    member, _, _ = setup_member(
        db,
        business,
        due=today() - timedelta(days=5),
        email="thandi@example.com",
    )
    db.add(
        MemberCommunicationPreference(
            member_id=member.id,
            business_id=business.id,
            preferred_channel="email",
        )
    )
    db.commit()

    candidate = run(db, business, kinds=["payment_overdue"]).candidates[0]

    assert candidate.channel == "email"
    assert candidate.recipient == "thandi@example.com"


def test_default_channel_is_whatsapp(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business)
    setup_member(
        db,
        business,
        due=today() - timedelta(days=5),
        email="thandi@example.com",
    )

    candidate = run(db, business, kinds=["payment_overdue"]).candidates[0]

    assert candidate.channel == "whatsapp"
    assert candidate.recipient == "27821234567"


# ============================================================
# TEMPLATES IN THE RULES
# ============================================================

def test_saved_wording_replaces_the_default(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business)
    setup_member(db, business, due=today() - timedelta(days=5))
    db.add(
        MessageTemplate(
            business_id=business.id,
            kind="payment_overdue",
            subject="Pay up {member_name}",
            body="{member_name}, {amount_due} is late.",
            is_active=True,
        )
    )
    db.commit()

    candidate = run(db, business, kinds=["payment_overdue"]).candidates[0]

    assert candidate.subject == "Pay up Thandi"
    assert candidate.body == "Thandi, R250.00 is late."


def test_switched_off_template_stops_that_kind(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business, 30)
    setup_member(db, business, due=today() - timedelta(days=25))
    db.add(
        MessageTemplate(
            business_id=business.id,
            kind="lapse_warning",
            subject="x",
            body="x",
            is_active=False,
        )
    )
    db.commit()

    plan = run(db, business)

    assert kinds_of(plan) == ["payment_overdue"]
    assert plan.disabled_kinds == ["lapse_warning"]


def test_every_kind_switched_off_plans_nothing(db, test_data):
    business = test_data["business_a"]
    set_lapse(db, business)
    setup_member(db, business, due=today() - timedelta(days=5))

    for kind in DEFAULT_TEMPLATES:
        db.add(
            MessageTemplate(
                business_id=business.id,
                kind=kind,
                subject="x",
                body="x",
                is_active=False,
            )
        )
    db.commit()

    plan = run(db, business)

    assert plan.candidates == []
    assert sorted(plan.disabled_kinds) == sorted(DEFAULT_TEMPLATES)


def test_templates_belong_to_one_business(db, test_data):
    business = test_data["business_a"]
    other = test_data["business_b"]
    set_lapse(db, business)
    setup_member(db, business, due=today() - timedelta(days=5))
    db.add(
        MessageTemplate(
            business_id=other.id,
            kind="payment_overdue",
            subject="other",
            body="other business wording",
            is_active=True,
        )
    )
    db.commit()

    body = run(db, business, kinds=["payment_overdue"]).candidates[0].body

    assert "other business wording" not in body


# ============================================================
# API: PREVIEW AND GENERATE
# ============================================================

def test_preview_shows_reminders_without_writing_any(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    set_lapse(db, business)
    setup_member(db, business, due=today() - timedelta(days=5))

    response = preview(
        client, auth_headers, test_data["manager"],
        kinds=["payment_overdue"],
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["items"]) == 1
    assert data["counts"] == {"payment_overdue": 1}
    assert data["items"][0]["channel"] == "whatsapp"
    assert data["items"][0]["member_name"] == "Thandi Nkosi"
    assert db.query(CommunicationMessage).count() == 0


def test_preview_with_no_body_uses_the_defaults(
    client, db, test_data, auth_headers
):
    set_lapse(db, test_data["business_a"])

    response = call(
        client, auth_headers, test_data["manager"],
        "POST", "/communications/reminders/preview",
    )

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_generate_queues_the_reminders(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    set_lapse(db, business)
    setup_member(db, business, due=today() - timedelta(days=5))
    setup_member(db, business, due=today() + timedelta(days=1))

    response = generate(client, auth_headers, test_data["manager"])

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["created"] == 2
    assert data["counts"] == {
        "payment_overdue": 1,
        "payment_due_soon": 1,
    }

    stored = db.query(CommunicationMessage).all()
    assert len(stored) == 2
    assert {m.status for m in stored} == {"queued"}
    assert all(m.created_by == test_data["manager"].id for m in stored)
    assert all(m.contribution_id is not None for m in stored)


def test_running_generate_twice_does_not_queue_duplicates(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    set_lapse(db, business, 30)
    setup_member(db, business, due=today() - timedelta(days=25))

    first = generate(client, auth_headers, test_data["manager"]).json()
    second = generate(client, auth_headers, test_data["manager"]).json()

    assert first["created"] == 2
    assert second["created"] == 0
    assert second["items"] == []
    assert second["already_queued"] >= 1
    assert db.query(CommunicationMessage).count() == 2


def test_cancelled_reminder_is_not_brought_back(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    set_lapse(db, business, 30)
    setup_member(db, business, due=today() - timedelta(days=25))
    generate(
        client, auth_headers, test_data["manager"], kinds=["lapse_warning"]
    )
    message = db.query(CommunicationMessage).one()

    call(
        client, auth_headers, test_data["manager"],
        "POST", f"/communications/messages/{message.id}/cancel",
    )
    again = generate(
        client, auth_headers, test_data["manager"], kinds=["lapse_warning"]
    ).json()

    assert again["created"] == 0
    assert db.query(CommunicationMessage).count() == 1


def test_generate_reports_who_was_skipped(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    set_lapse(db, business)
    setup_member(
        db, business, due=today() - timedelta(days=5), phone=None
    )

    data = generate(
        client, auth_headers, test_data["manager"],
        kinds=["payment_overdue"],
    ).json()

    assert data["created"] == 0
    assert [s["reason"] for s in data["skipped"]] == ["no_contact"]


def test_generate_reports_switched_off_kinds(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    set_lapse(db, business)
    db.add(
        MessageTemplate(
            business_id=business.id,
            kind="lapsed",
            subject="x",
            body="x",
            is_active=False,
        )
    )
    db.commit()

    data = preview(client, auth_headers, test_data["manager"]).json()

    assert data["disabled_kinds"] == ["lapsed"]


def test_generate_audit_records_counts_not_wording_or_numbers(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    set_lapse(db, business)
    setup_member(db, business, due=today() - timedelta(days=5))

    generate(
        client, auth_headers, test_data["manager"],
        kinds=["payment_overdue"],
    )

    log = audits(db, "communication.reminders_generated")[-1]

    assert log.details["created"] == 1
    assert log.details["counts"] == {"payment_overdue": 1}
    assert "27821234567" not in str(log.details)
    assert "Thandi" not in str(log.details)


def test_generate_with_nothing_to_send_writes_no_audit(
    client, db, test_data, auth_headers
):
    set_lapse(db, test_data["business_a"])

    generate(client, auth_headers, test_data["manager"])

    assert audits(db, "communication.reminders_generated") == []


def test_generate_rejects_silly_options(
    client, db, test_data, auth_headers
):
    for options in (
        {"days_before": -1},
        {"days_before": 99},
        {"warning_days": 0},
        {"kinds": ["nonsense"]},
        {"unknown": 1},
    ):
        response = generate(
            client, auth_headers, test_data["manager"], **options
        )

        assert response.status_code == 422, options


# ============================================================
# API: MESSAGES
# ============================================================

def test_list_shows_message_with_a_ready_link(
    client, db, test_data, auth_headers
):
    queue_one(client, auth_headers, db, test_data)

    response = messages(client, auth_headers, test_data["manager"])

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 1
    assert data["counts"] == {"queued": 1, "sent": 0, "cancelled": 0}

    item = data["items"][0]
    assert item["member_name"] == "Thandi Nkosi"
    assert item["membership_number"].startswith("MS-")
    assert item["status"] == "queued"
    assert item["kind"] == "payment_overdue"
    assert item["action_url"].startswith("https://wa.me/27821234567?text=")


def test_list_filters_by_status_kind_and_member(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    set_lapse(db, business, 30)
    member, _, _ = setup_member(
        db, business, due=today() - timedelta(days=25)
    )
    setup_member(db, business, due=today() - timedelta(days=5))

    generate(client, auth_headers, test_data["manager"])
    first = db.query(CommunicationMessage).first()
    call(
        client, auth_headers, test_data["manager"],
        "POST", f"/communications/messages/{first.id}/mark-sent",
    )

    manager = test_data["manager"]

    everything = messages(client, auth_headers, manager).json()

    assert everything["total"] == 3
    assert everything["counts"] == {"queued": 2, "sent": 1, "cancelled": 0}
    assert messages(
        client, auth_headers, manager, status="sent"
    ).json()["counts"] == {"queued": 2, "sent": 1, "cancelled": 0}
    assert messages(
        client, auth_headers, manager, status="sent"
    ).json()["total"] == 1
    assert messages(
        client, auth_headers, manager, status="queued"
    ).json()["total"] == 2
    assert messages(
        client, auth_headers, manager, kind="lapse_warning"
    ).json()["total"] == 1
    assert messages(
        client, auth_headers, manager, member_id=str(member.id)
    ).json()["total"] == 2


def test_status_counts_ignore_the_status_filter(
    client, db, test_data, auth_headers
):
    queue_one(client, auth_headers, db, test_data)

    data = messages(
        client, auth_headers, test_data["manager"], status="sent"
    ).json()

    assert data["total"] == 0
    assert data["counts"]["queued"] == 1


def test_list_rejects_unknown_status(
    client, db, test_data, auth_headers
):
    response = messages(
        client, auth_headers, test_data["manager"], status="lost"
    )

    assert response.status_code == 422


def test_list_filters_by_branch(client, db, test_data, auth_headers):
    business = test_data["business_a"]
    set_lapse(db, business)
    branch = Branch(
        business_id=business.id, name="Soweto", code="SOW", is_main=False
    )
    db.add(branch)
    db.commit()

    setup_member(
        db, business, due=today() - timedelta(days=5), branch=branch
    )
    setup_member(db, business, due=today() - timedelta(days=5))
    generate(
        client, auth_headers, test_data["manager"],
        kinds=["payment_overdue"],
    )

    data = messages(
        client, auth_headers, test_data["manager"],
        branch_id=str(branch.id),
    ).json()

    assert data["total"] == 1


def test_list_pages(client, db, test_data, auth_headers):
    business = test_data["business_a"]
    set_lapse(db, business)

    for _ in range(3):
        setup_member(db, business, due=today() - timedelta(days=5))

    generate(
        client, auth_headers, test_data["manager"],
        kinds=["payment_overdue"],
    )

    first = messages(
        client, auth_headers, test_data["manager"], limit=2
    ).json()
    second = messages(
        client, auth_headers, test_data["manager"], limit=2, offset=2
    ).json()

    assert first["total"] == 3
    assert len(first["items"]) == 2
    assert len(second["items"]) == 1
    assert not {i["id"] for i in first["items"]} & {
        i["id"] for i in second["items"]
    }


def test_list_rejects_bad_paging(client, db, test_data, auth_headers):
    manager = test_data["manager"]

    assert messages(
        client, auth_headers, manager, limit=0
    ).status_code == 422
    assert messages(
        client, auth_headers, manager, limit=500
    ).status_code == 422
    assert messages(
        client, auth_headers, manager, offset=-1
    ).status_code == 422


def test_mark_sent_records_who_and_when(
    client, db, test_data, auth_headers
):
    message_id = queue_one(client, auth_headers, db, test_data)

    response = call(
        client, auth_headers, test_data["staff"],
        "POST", f"/communications/messages/{message_id}/mark-sent",
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "sent"
    assert response.json()["sent_at"] is not None

    db.expire_all()
    stored = db.get(CommunicationMessage, message_id)
    assert stored.sent_by == test_data["staff"].id


def test_mark_sent_is_audited_without_wording(
    client, db, test_data, auth_headers
):
    message_id = queue_one(client, auth_headers, db, test_data)

    call(
        client, auth_headers, test_data["manager"],
        "POST", f"/communications/messages/{message_id}/mark-sent",
    )

    log = audits(db, "communication.message_sent")[-1]

    assert log.entity_id == message_id
    assert log.details["kind"] == "payment_overdue"
    assert log.details["channel"] == "whatsapp"
    assert "27821234567" not in str(log.details)
    assert "Hello" not in str(log.details)


def test_a_sent_message_cannot_be_sent_or_cancelled_again(
    client, db, test_data, auth_headers
):
    message_id = queue_one(client, auth_headers, db, test_data)
    manager = test_data["manager"]

    call(
        client, auth_headers, manager,
        "POST", f"/communications/messages/{message_id}/mark-sent",
    )

    assert call(
        client, auth_headers, manager,
        "POST", f"/communications/messages/{message_id}/mark-sent",
    ).status_code == 409
    assert call(
        client, auth_headers, manager,
        "POST", f"/communications/messages/{message_id}/cancel",
    ).status_code == 409


def test_cancel_keeps_the_message_and_the_reason(
    client, db, test_data, auth_headers
):
    message_id = queue_one(client, auth_headers, db, test_data)

    response = call(
        client, auth_headers, test_data["manager"],
        "POST", f"/communications/messages/{message_id}/cancel",
        json={"reason": "  Paid by EFT this morning  "},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "cancelled"
    assert data["cancel_reason"] == "Paid by EFT this morning"
    assert data["cancelled_at"] is not None


def test_cancel_works_without_a_body(
    client, db, test_data, auth_headers
):
    message_id = queue_one(client, auth_headers, db, test_data)

    response = call(
        client, auth_headers, test_data["manager"],
        "POST", f"/communications/messages/{message_id}/cancel",
    )

    assert response.status_code == 200
    assert response.json()["cancel_reason"] is None


def test_cancel_audit_notes_a_reason_without_copying_it(
    client, db, test_data, auth_headers
):
    message_id = queue_one(client, auth_headers, db, test_data)

    call(
        client, auth_headers, test_data["manager"],
        "POST", f"/communications/messages/{message_id}/cancel",
        json={"reason": "Private family matter"},
    )

    log = audits(db, "communication.message_cancelled")[-1]

    assert log.details["has_reason"] is True
    assert "Private family matter" not in str(log.details)


def test_cancelled_message_cannot_be_sent(
    client, db, test_data, auth_headers
):
    message_id = queue_one(client, auth_headers, db, test_data)
    manager = test_data["manager"]

    call(
        client, auth_headers, manager,
        "POST", f"/communications/messages/{message_id}/cancel",
    )

    assert call(
        client, auth_headers, manager,
        "POST", f"/communications/messages/{message_id}/mark-sent",
    ).status_code == 409


def test_unknown_message_is_not_found(
    client, db, test_data, auth_headers
):
    for action in ("mark-sent", "cancel"):
        response = call(
            client, auth_headers, test_data["manager"],
            "POST", f"/communications/messages/{uuid.uuid4()}/{action}",
        )

        assert response.status_code == 404


# ============================================================
# API: ONE-OFF MESSAGES
# ============================================================

def write(client, auth_headers, user, member, **fields):
    return call(
        client, auth_headers, user,
        "POST", "/communications/messages",
        json={"member_id": str(member.id), "body": "Hello", **fields},
    )


def test_staff_can_write_a_message_to_a_member(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])

    response = write(
        client, auth_headers, test_data["staff"], member,
        body="  Your plan documents are ready.  ",
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["kind"] == "custom"
    assert data["status"] == "queued"
    assert data["body"] == "Your plan documents are ready."
    assert data["channel"] == "whatsapp"
    assert data["recipient"] == "27821234567"
    assert data["membership_id"] is None


def test_message_uses_the_chosen_channel(
    client, db, test_data, auth_headers
):
    member = make_member(
        db, test_data["business_a"], email="thandi@example.com"
    )

    response = write(
        client, auth_headers, test_data["staff"], member,
        channel="email", subject="Documents",
    )

    assert response.status_code == 201
    data = response.json()
    assert data["channel"] == "email"
    assert data["recipient"] == "thandi@example.com"
    assert data["subject"] == "Documents"
    assert data["action_url"].startswith("mailto:thandi@example.com")


def test_message_uses_the_members_preferred_channel(
    client, db, test_data, auth_headers
):
    member = make_member(
        db, test_data["business_a"], email="thandi@example.com"
    )
    db.add(
        MemberCommunicationPreference(
            member_id=member.id,
            business_id=member.business_id,
            preferred_channel="sms",
        )
    )
    db.commit()

    data = write(
        client, auth_headers, test_data["staff"], member
    ).json()

    assert data["channel"] == "sms"


def test_message_refused_for_a_member_who_opted_out(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])
    db.add(
        MemberCommunicationPreference(
            member_id=member.id,
            business_id=member.business_id,
            preferred_channel="whatsapp",
            opted_out=True,
            opted_out_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    response = write(client, auth_headers, test_data["staff"], member)

    assert response.status_code == 409
    assert "opted out" in response.json()["detail"]
    assert db.query(CommunicationMessage).count() == 0


def test_message_refused_without_any_contact_detail(
    client, db, test_data, auth_headers
):
    member = make_member(
        db, test_data["business_a"], phone=None, email=None
    )

    response = write(client, auth_headers, test_data["staff"], member)

    assert response.status_code == 409


def test_message_refused_when_the_chosen_channel_has_no_detail(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"], email=None)

    response = write(
        client, auth_headers, test_data["staff"], member, channel="email"
    )

    assert response.status_code == 409
    assert "email" in response.json()["detail"]


def test_message_validation(client, db, test_data, auth_headers):
    member = make_member(db, test_data["business_a"])
    staff = test_data["staff"]

    assert write(
        client, auth_headers, staff, member, body="   "
    ).status_code == 422
    assert write(
        client, auth_headers, staff, member, body="x" * 1001
    ).status_code == 422
    assert write(
        client, auth_headers, staff, member, channel="pigeon"
    ).status_code == 422
    assert call(
        client, auth_headers, staff, "POST", "/communications/messages",
        json={"body": "no member"},
    ).status_code == 422


def test_message_to_unknown_member_is_not_found(
    client, db, test_data, auth_headers
):
    response = call(
        client, auth_headers, test_data["staff"],
        "POST", "/communications/messages",
        json={"member_id": str(uuid.uuid4()), "body": "Hello"},
    )

    assert response.status_code == 404


def test_written_message_is_audited_without_wording(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])

    write(
        client, auth_headers, test_data["staff"], member,
        body="Sorry for your loss, Mrs Nkosi",
    )

    log = audits(db, "communication.message_created")[-1]

    assert log.details["kind"] == "custom"
    assert "Nkosi" not in str(log.details)
    assert "27821234567" not in str(log.details)


# ============================================================
# API: TEMPLATES
# ============================================================

def test_templates_start_as_the_built_in_wording(
    client, db, test_data, auth_headers
):
    response = call(
        client, auth_headers, test_data["staff"],
        "GET", "/communications/templates",
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert [t["kind"] for t in data["templates"]] == [
        "payment_due_soon",
        "payment_overdue",
        "lapse_warning",
        "lapsed",
    ]
    assert all(t["is_default"] and t["is_active"] for t in data["templates"])
    assert {p["name"] for p in data["placeholders"]} == set(PLACEHOLDERS)


def test_manager_can_change_the_wording(
    client, db, test_data, auth_headers
):
    response = call(
        client, auth_headers, test_data["manager"],
        "PUT", "/communications/templates/payment_overdue",
        json={
            "subject": "  Late payment  ",
            "body": "Hi {member_name}, please pay {amount_due}.",
            "is_active": True,
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["subject"] == "Late payment"
    assert data["is_default"] is False

    listed = call(
        client, auth_headers, test_data["staff"],
        "GET", "/communications/templates",
    ).json()["templates"]

    overdue = next(t for t in listed if t["kind"] == "payment_overdue")
    assert overdue["body"] == "Hi {member_name}, please pay {amount_due}."
    assert db.query(MessageTemplate).count() == 1


def test_changing_the_wording_twice_keeps_one_row(
    client, db, test_data, auth_headers
):
    for body in ("First {member_name}", "Second {member_name}"):
        call(
            client, auth_headers, test_data["manager"],
            "PUT", "/communications/templates/lapsed",
            json={"subject": "S", "body": body, "is_active": True},
        )

    rows = db.query(MessageTemplate).all()

    assert len(rows) == 1
    assert rows[0].body == "Second {member_name}"


def test_switching_a_template_off(client, db, test_data, auth_headers):
    response = call(
        client, auth_headers, test_data["manager"],
        "PUT", "/communications/templates/lapsed",
        json={"subject": "S", "body": "B", "is_active": False},
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_unknown_placeholder_is_refused(
    client, db, test_data, auth_headers
):
    response = call(
        client, auth_headers, test_data["manager"],
        "PUT", "/communications/templates/lapsed",
        json={"subject": "S", "body": "Hi {nickname}", "is_active": True},
    )

    assert response.status_code == 422
    assert "{nickname}" in response.json()["detail"]
    assert db.query(MessageTemplate).count() == 0


def test_blank_or_oversized_wording_is_refused(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]

    for body in (
        {"subject": " ", "body": "B"},
        {"subject": "S", "body": "  "},
        {"subject": "S", "body": "x" * 1001},
        {"subject": "S" * 201, "body": "B"},
        {"subject": "S", "body": "B", "extra": 1},
    ):
        response = call(
            client, auth_headers, manager,
            "PUT", "/communications/templates/lapsed", json=body,
        )

        assert response.status_code == 422, body


def test_unknown_template_kind_is_not_found(
    client, db, test_data, auth_headers
):
    response = call(
        client, auth_headers, test_data["manager"],
        "PUT", "/communications/templates/custom",
        json={"subject": "S", "body": "B", "is_active": True},
    )

    assert response.status_code == 404


def test_template_change_is_audited(client, db, test_data, auth_headers):
    call(
        client, auth_headers, test_data["manager"],
        "PUT", "/communications/templates/lapsed",
        json={"subject": "New", "body": "New body", "is_active": False},
    )

    log = audits(db, "communication_template.updated")[-1]

    assert log.details["kind"] == "lapsed"
    assert log.details["changes"]["is_active"] == {
        "old": True,
        "new": False,
    }
    assert log.details["changes"]["subject"]["new"] == "New"


def test_saving_identical_wording_writes_no_audit(
    client, db, test_data, auth_headers
):
    subject, body = DEFAULT_TEMPLATES["lapsed"]

    call(
        client, auth_headers, test_data["manager"],
        "PUT", "/communications/templates/lapsed",
        json={"subject": subject, "body": body, "is_active": True},
    )

    assert audits(db, "communication_template.updated") == []


def test_new_wording_is_used_the_next_time_reminders_are_made(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    set_lapse(db, business)
    setup_member(db, business, due=today() - timedelta(days=5))

    call(
        client, auth_headers, test_data["manager"],
        "PUT", "/communications/templates/payment_overdue",
        json={
            "subject": "Late",
            "body": "{member_name} owes {amount_due}",
            "is_active": True,
        },
    )

    data = generate(
        client, auth_headers, test_data["manager"],
        kinds=["payment_overdue"],
    ).json()

    assert data["items"][0]["body"] == "Thandi owes R250.00"


# ============================================================
# API: PREFERENCES
# ============================================================

def prefs(client, auth_headers, user, member, method="GET", **fields):
    return call(
        client, auth_headers, user,
        method, f"/members/{member.id}/communication-preferences",
        json=fields if method == "PATCH" else None,
    )


def test_preferences_default_when_nothing_is_saved(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])

    response = prefs(client, auth_headers, test_data["staff"], member)

    assert response.status_code == 200, response.text
    assert response.json() == {
        "member_id": str(member.id),
        "preferred_channel": "whatsapp",
        "opted_out": False,
        "opted_out_at": None,
        "opt_out_reason": None,
    }
    assert db.query(MemberCommunicationPreference).count() == 0


def test_choose_a_preferred_channel(client, db, test_data, auth_headers):
    member = make_member(db, test_data["business_a"])

    response = prefs(
        client, auth_headers, test_data["staff"], member,
        method="PATCH", preferred_channel="sms",
    )

    assert response.status_code == 200, response.text
    assert response.json()["preferred_channel"] == "sms"
    assert response.json()["opted_out"] is False


def test_opting_out_records_when_and_why(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])

    response = prefs(
        client, auth_headers, test_data["staff"], member,
        method="PATCH", opted_out=True, opt_out_reason="  Asked on the phone ",
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["opted_out"] is True
    assert data["opted_out_at"] is not None
    assert data["opt_out_reason"] == "Asked on the phone"


def test_opting_out_again_keeps_the_original_time(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])
    staff = test_data["staff"]

    first = prefs(
        client, auth_headers, staff, member,
        method="PATCH", opted_out=True,
    ).json()
    second = prefs(
        client, auth_headers, staff, member,
        method="PATCH", opted_out=True, opt_out_reason="Still no",
    ).json()

    assert second["opted_out_at"] == first["opted_out_at"]


def test_opting_back_in_clears_the_time_and_reason(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])
    staff = test_data["staff"]

    prefs(
        client, auth_headers, staff, member,
        method="PATCH", opted_out=True, opt_out_reason="No thanks",
    )
    data = prefs(
        client, auth_headers, staff, member,
        method="PATCH", opted_out=False,
    ).json()

    assert data["opted_out"] is False
    assert data["opted_out_at"] is None
    assert data["opt_out_reason"] is None


def test_a_reason_is_ignored_unless_the_member_has_opted_out(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])

    data = prefs(
        client, auth_headers, test_data["staff"], member,
        method="PATCH", opt_out_reason="Not opted out",
    ).json()

    assert data["opt_out_reason"] is None


def test_choosing_a_channel_keeps_an_existing_opt_out(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])
    staff = test_data["staff"]

    prefs(
        client, auth_headers, staff, member,
        method="PATCH", opted_out=True,
    )
    data = prefs(
        client, auth_headers, staff, member,
        method="PATCH", preferred_channel="email",
    ).json()

    assert data["opted_out"] is True
    assert data["preferred_channel"] == "email"


def test_null_values_do_not_wipe_the_settings(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])
    staff = test_data["staff"]

    prefs(
        client, auth_headers, staff, member,
        method="PATCH", preferred_channel="email", opted_out=True,
    )
    data = prefs(
        client, auth_headers, staff, member,
        method="PATCH", preferred_channel=None, opted_out=None,
    ).json()

    assert data["preferred_channel"] == "email"
    assert data["opted_out"] is True


def test_preference_validation(client, db, test_data, auth_headers):
    member = make_member(db, test_data["business_a"])
    staff = test_data["staff"]

    assert prefs(
        client, auth_headers, staff, member,
        method="PATCH", preferred_channel="pigeon",
    ).status_code == 422
    assert prefs(
        client, auth_headers, staff, member,
        method="PATCH", mystery=True,
    ).status_code == 422


def test_opt_out_stops_reminders_straight_away(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    set_lapse(db, business)
    member, _, _ = setup_member(
        db, business, due=today() - timedelta(days=5)
    )

    prefs(
        client, auth_headers, test_data["staff"], member,
        method="PATCH", opted_out=True,
    )
    data = generate(
        client, auth_headers, test_data["manager"],
        kinds=["payment_overdue"],
    ).json()

    assert data["created"] == 0
    assert [s["reason"] for s in data["skipped"]] == ["opted_out"]


def test_preference_change_is_audited_with_the_reason_redacted(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])

    prefs(
        client, auth_headers, test_data["staff"], member,
        method="PATCH", opted_out=True,
        opt_out_reason="Bereaved, asked us to stop",
    )

    log = audits(db, "communication_preferences.updated")[-1]
    changes = log.details["changes"]

    assert log.entity_id == member.id
    assert changes["opted_out"] == {"old": False, "new": True}
    assert changes["opt_out_reason"]["old"] == "[redacted]"
    assert changes["opt_out_reason"]["new"] == "[redacted]"
    assert "Bereaved" not in str(log.details)


def test_repeating_the_same_preference_writes_no_new_audit(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])
    staff = test_data["staff"]

    prefs(
        client, auth_headers, staff, member,
        method="PATCH", preferred_channel="sms",
    )
    prefs(
        client, auth_headers, staff, member,
        method="PATCH", preferred_channel="sms",
    )

    assert len(audits(db, "communication_preferences.updated")) == 1


def test_preferences_for_unknown_member_are_not_found(
    client, db, test_data, auth_headers
):
    ghost = type("Ghost", (), {"id": uuid.uuid4()})()

    assert prefs(
        client, auth_headers, test_data["staff"], ghost
    ).status_code == 404
    assert prefs(
        client, auth_headers, test_data["staff"], ghost,
        method="PATCH", preferred_channel="sms",
    ).status_code == 404


# ============================================================
# PERMISSIONS AND ISOLATION
# ============================================================

def test_every_role_that_should_has_the_permissions(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])

    for user in (
        test_data["main_admin"],
        test_data["manager"],
        test_data["staff"],
    ):
        assert messages(client, auth_headers, user).status_code == 200
        assert write(
            client, auth_headers, user, member
        ).status_code == 201


def test_staff_cannot_change_templates_but_manager_can(
    client, db, test_data, auth_headers
):
    body = {"subject": "S", "body": "B", "is_active": True}
    path = "/communications/templates/lapsed"

    assert call(
        client, auth_headers, test_data["staff"], "PUT", path, json=body
    ).status_code == 403
    assert call(
        client, auth_headers, test_data["manager"], "PUT", path, json=body
    ).status_code == 200
    assert call(
        client, auth_headers, test_data["main_admin"], "PUT", path,
        json=body,
    ).status_code == 200


def test_view_permission_guards_every_read(
    client, db, test_data, auth_headers
):
    staff = test_data["staff"]
    member = make_member(db, test_data["business_a"])
    deny(db, staff, "communications.view")

    assert messages(client, auth_headers, staff).status_code == 403
    assert call(
        client, auth_headers, staff, "GET", "/communications/templates"
    ).status_code == 403
    assert preview(client, auth_headers, staff).status_code == 403
    assert prefs(client, auth_headers, staff, member).status_code == 403


def test_send_permission_guards_every_change(
    client, db, test_data, auth_headers
):
    message_id = queue_one(client, auth_headers, db, test_data)
    staff = test_data["staff"]
    member = make_member(db, test_data["business_a"])
    deny(db, staff, "communications.send")

    assert generate(client, auth_headers, staff).status_code == 403
    assert write(client, auth_headers, staff, member).status_code == 403
    assert call(
        client, auth_headers, staff,
        "POST", f"/communications/messages/{message_id}/mark-sent",
    ).status_code == 403
    assert call(
        client, auth_headers, staff,
        "POST", f"/communications/messages/{message_id}/cancel",
    ).status_code == 403
    assert prefs(
        client, auth_headers, staff, member,
        method="PATCH", preferred_channel="sms",
    ).status_code == 403

    # Reading is unaffected.
    assert messages(client, auth_headers, staff).status_code == 200


def test_nothing_is_open_without_logging_in(client, db, test_data):
    assert client.get("/communications/messages").status_code in (401, 403)
    assert client.get("/communications/templates").status_code in (401, 403)
    assert client.post(
        "/communications/reminders/generate", json={}
    ).status_code in (401, 403)


def test_another_business_cannot_see_or_touch_messages(
    client, db, test_data, auth_headers
):
    message_id = queue_one(client, auth_headers, db, test_data)
    outsider = test_data["other_business_manager"]

    assert messages(
        client, auth_headers, outsider
    ).json()["total"] == 0
    assert call(
        client, auth_headers, outsider,
        "POST", f"/communications/messages/{message_id}/mark-sent",
    ).status_code == 404
    assert call(
        client, auth_headers, outsider,
        "POST", f"/communications/messages/{message_id}/cancel",
    ).status_code == 404

    db.expire_all()
    assert db.get(CommunicationMessage, message_id).status == "queued"


def test_another_business_cannot_reach_a_members_preferences_or_inbox(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])
    outsider = test_data["other_business_manager"]

    assert prefs(
        client, auth_headers, outsider, member
    ).status_code == 404
    assert prefs(
        client, auth_headers, outsider, member,
        method="PATCH", opted_out=True,
    ).status_code == 404
    assert write(
        client, auth_headers, outsider, member
    ).status_code == 404
    assert db.query(MemberCommunicationPreference).count() == 0


def test_another_business_gets_its_own_templates_and_reminders(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    set_lapse(db, business)
    setup_member(db, business, due=today() - timedelta(days=5))
    outsider = test_data["other_business_manager"]

    call(
        client, auth_headers, test_data["manager"],
        "PUT", "/communications/templates/lapsed",
        json={"subject": "Mine", "body": "Mine", "is_active": False},
    )

    theirs = call(
        client, auth_headers, outsider, "GET", "/communications/templates"
    ).json()["templates"]

    assert all(t["is_default"] and t["is_active"] for t in theirs)
    assert generate(
        client, auth_headers, outsider
    ).json()["created"] == 0


# ============================================================
# DATABASE RULES
# ============================================================

def raw_message(db, business, member, **overrides):
    values = dict(
        business_id=business.id,
        member_id=member.id,
        kind="custom",
        channel="whatsapp",
        recipient="27821234567",
        body="Hello",
        status="queued",
    )
    values.update(overrides)

    return CommunicationMessage(**values)


def test_database_refuses_sent_without_a_time(db, test_data):
    business = test_data["business_a"]
    member = make_member(db, business)

    db.add(raw_message(db, business, member, status="sent"))

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_database_refuses_a_time_on_an_unsent_message(db, test_data):
    business = test_data["business_a"]
    member = make_member(db, business)

    db.add(
        raw_message(
            db, business, member, sent_at=datetime.now(timezone.utc)
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


@pytest.mark.parametrize(
    "field,value",
    [("status", "lost"), ("channel", "pigeon"), ("kind", "spam")],
)
def test_database_refuses_unknown_values(db, test_data, field, value):
    business = test_data["business_a"]
    member = make_member(db, business)

    db.add(raw_message(db, business, member, **{field: value}))

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_database_refuses_the_same_reminder_twice(db, test_data):
    business = test_data["business_a"]
    member = make_member(db, business)

    db.add(raw_message(db, business, member, dedupe_key="same"))
    db.commit()
    db.add(raw_message(db, business, member, dedupe_key="same"))

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_database_allows_many_messages_without_a_dedupe_key(db, test_data):
    business = test_data["business_a"]
    member = make_member(db, business)

    db.add(raw_message(db, business, member))
    db.add(raw_message(db, business, member))
    db.commit()

    assert db.query(CommunicationMessage).count() == 2


def test_the_same_dedupe_key_is_fine_in_another_business(db, test_data):
    first = make_member(db, test_data["business_a"])
    second = make_member(db, test_data["business_b"])

    db.add(
        raw_message(
            db, test_data["business_a"], first, dedupe_key="same"
        )
    )
    db.add(
        raw_message(
            db, test_data["business_b"], second, dedupe_key="same"
        )
    )
    db.commit()

    assert db.query(CommunicationMessage).count() == 2


def test_database_ties_opt_out_to_a_time(db, test_data):
    business = test_data["business_a"]
    member = make_member(db, business)

    db.add(
        MemberCommunicationPreference(
            member_id=member.id,
            business_id=business.id,
            preferred_channel="whatsapp",
            opted_out=True,
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_database_allows_one_template_per_kind_per_business(db, test_data):
    business = test_data["business_a"]

    db.add(
        MessageTemplate(
            business_id=business.id, kind="lapsed", subject="a", body="a"
        )
    )
    db.commit()
    db.add(
        MessageTemplate(
            business_id=business.id, kind="lapsed", subject="b", body="b"
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_deleting_a_member_removes_their_messages_and_preferences(
    db, test_data
):
    business = test_data["business_a"]
    member = make_member(db, business)

    db.add(raw_message(db, business, member))
    db.add(
        MemberCommunicationPreference(
            member_id=member.id,
            business_id=business.id,
            preferred_channel="sms",
        )
    )
    db.commit()

    db.delete(member)
    db.commit()

    assert db.query(CommunicationMessage).count() == 0
    assert db.query(MemberCommunicationPreference).count() == 0
