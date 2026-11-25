from app.services.payfast import checkout_url, signature, valid_signature


def test_payfast_signature_is_stable_for_checkout_fields():
    fields = [
        ("merchant_id", "10000100"),
        ("amount", "499.00"),
        ("email_address", "billing@example.co.za"),
    ]
    assert signature(fields, "test passphrase") == signature(fields, "test passphrase")


def test_payfast_signature_changes_when_amount_changes():
    fields = [("amount", "499.00"), ("m_payment_id", "LINDA-123")]
    signed = signature(fields, "test passphrase")
    changed = [("amount", "599.00"), ("m_payment_id", "LINDA-123")]
    assert signed != signature(changed, "test passphrase")


def test_payfast_itn_signature_validation():
    fields = [("payment_status", "COMPLETE"), ("amount_gross", "499.00")]
    signed = signature(fields, "test passphrase")
    assert valid_signature(fields, signed, "test passphrase")
    assert not valid_signature(fields, "0" * 32, "test passphrase")
    assert not valid_signature(fields, signed, "wrong passphrase")


def test_payfast_uses_sandbox_and_live_checkout_hosts():
    assert checkout_url(sandbox=True) == "https://sandbox.payfast.co.za/eng/process"
    assert checkout_url(sandbox=False) == "https://www.payfast.co.za/eng/process"
