"""Death paperwork rules.

The checklist of forms, permits and certificates a funeral needs
depends on how the person died and how they will be laid to rest.
Pure rules with no HTTP concerns.

The standard items follow South African practice: a notification of
death, a death report, a burial order and a death certificate from
Home Affairs, formal identification at the mortuary, and extra
authority for unnatural deaths, cremation, repatriation and infectious
remains. An operator can add custom items for anything else.
"""

from dataclasses import dataclass


class PaperworkError(Exception):
    """A paperwork rule was violated."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class StandardItem:
    item_type: str
    label: str
    required: bool = True


NOTIFICATION_OF_DEATH = StandardItem(
    "notification_of_death", "Notification of death (BI-1663)"
)
FORMAL_IDENTIFICATION = StandardItem(
    "formal_identification", "Formal identification at the mortuary"
)
DEATH_REPORT = StandardItem(
    "death_report", "Death report (BI-1680)"
)
BURIAL_ORDER = StandardItem(
    "burial_order", "Burial order (BI-14)"
)
DEATH_CERTIFICATE = StandardItem(
    "death_certificate", "Death certificate"
)
INFORMANT_ID_COPY = StandardItem(
    "informant_id_copy", "Copy of the informant's ID", required=False
)

POLICE_CASE = StandardItem(
    "police_case_registered", "Police case registered (SAPS)"
)
POST_MORTEM_RELEASE = StandardItem(
    "post_mortem_release", "Post-mortem and release by forensic pathology"
)

CREMATION_PERMIT = StandardItem(
    "cremation_permit", "Cremation permit"
)

EXPORT_PERMIT = StandardItem(
    "export_permit", "Export permit"
)
EMBALMING_CERTIFICATE = StandardItem(
    "embalming_certificate", "Embalming certificate"
)

INFECTIOUS_DECLARATION = StandardItem(
    "infectious_remains_declaration",
    "Medical declaration for infectious remains",
)


def standard_items(
    *,
    manner_of_death: str,
    disposal_method: str,
    infectious_remains: bool,
) -> list[StandardItem]:
    """The checklist for a case, in the order it is worked through."""

    items = [
        NOTIFICATION_OF_DEATH,
        FORMAL_IDENTIFICATION,
    ]

    if manner_of_death == "unnatural":
        items += [POLICE_CASE, POST_MORTEM_RELEASE]

    items += [DEATH_REPORT, DEATH_CERTIFICATE]

    if disposal_method == "burial":
        items.append(BURIAL_ORDER)
    elif disposal_method == "cremation":
        items.append(CREMATION_PERMIT)
    elif disposal_method == "repatriation":
        items += [EXPORT_PERMIT, EMBALMING_CERTIFICATE]

    if infectious_remains:
        items.append(INFECTIOUS_DECLARATION)

    items.append(INFORMANT_ID_COPY)

    return items


def validate_item_update(
    *,
    required: bool,
    new_status: str,
    notes: str | None,
) -> None:
    """A required item may only be waived with a reason."""

    if (
        new_status == "not_applicable"
        and required
        and not (notes and notes.strip())
    ):
        raise PaperworkError(
            422,
            "Give a reason in the notes to mark a required item "
            "as not applicable",
        )


def paperwork_summary(items) -> dict:
    """How far the paperwork has got.

    A case is ready when every required item is obtained or waived.
    """

    required = [item for item in items if item.required]

    outstanding = [
        item.label for item in required if item.status == "pending"
    ]

    done = len(required) - len(outstanding)

    return {
        "required_total": len(required),
        "required_done": done,
        "outstanding": outstanding,
        "ready": bool(required) and not outstanding,
    }
