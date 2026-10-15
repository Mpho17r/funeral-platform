"""Identity number checks."""

from datetime import date


def validate_sa_id(number: str | None) -> str | None:
    """Check a South African ID number.

    Returns None when it is valid, otherwise a short reason. The
    number must be 13 digits, start with a real date of birth, have a
    citizenship digit of 0 or 1 and pass the Luhn check digit.
    """

    if number is None:
        return None

    if len(number) != 13 or not number.isdigit():
        return "A South African ID number has 13 digits"

    year = int(number[0:2])
    month = int(number[2:4])
    day = int(number[4:6])

    # The century is not part of the number, so a date that is valid
    # in either century is accepted.
    valid_date = False

    for century in (1900, 2000):
        try:
            date(century + year, month, day)
            valid_date = True
            break
        except ValueError:
            continue

    if not valid_date:
        return "The ID number does not start with a valid date of birth"

    if number[10] not in ("0", "1"):
        return "The ID number has an invalid citizenship digit"

    total = 0

    for index, char in enumerate(reversed(number)):
        digit = int(char)

        if index % 2 == 1:
            digit *= 2

            if digit > 9:
                digit -= 9

        total += digit

    if total % 10 != 0:
        return "The ID number check digit is wrong"

    return None


def normalise_identity_number(value: str | None) -> str | None:
    """Tidy and check an identity document number for a person record.

    A 13-digit number is treated as a South African ID and must pass the
    full check, so a mistyped digit is caught when it is entered. Any
    other value is accepted as a foreign passport or permit number if it
    is 5 to 20 letters or digits. Spaces and dashes are removed. Returns
    None for an empty value and raises ValueError with a short reason.
    """

    if value is None:
        return None

    cleaned = "".join(
        char for char in value.strip() if char not in " -"
    ).upper()

    if not cleaned:
        return None

    if cleaned.isdigit() and len(cleaned) == 13:
        reason = validate_sa_id(cleaned)

        if reason is not None:
            raise ValueError(reason)

        return cleaned

    if cleaned.isdigit() and len(cleaned) != 13 and len(cleaned) >= 8:
        # Looks like a South African ID with a missing or extra digit.
        raise ValueError("A South African ID number has 13 digits")

    if not (5 <= len(cleaned) <= 20 and cleaned.isalnum()):
        raise ValueError(
            "Enter a 13-digit South African ID number or a passport "
            "number of 5 to 20 letters and digits"
        )

    return cleaned
