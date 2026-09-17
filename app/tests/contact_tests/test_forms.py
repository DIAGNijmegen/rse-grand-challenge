import pytest

from grandchallenge.contact.forms import ContactForm


def test_valid_form():
    form = ContactForm(
        data={
            "name": "Jane Doe",
            "email": "jane@example.org",
            "message": "I have a question.",
            "accept_privacy_policy": True,
            "subject": "",
            "ref": "",
            "c0": "AAA",
            "c1": "BBB",
            "c2": "BBBAAA",
        }
    )
    assert form.is_valid(), form.errors
    assert form.honeypot_tripped is False
    assert form.challenge_passed is True


def test_blank_message_is_invalid():
    form = ContactForm(
        data={
            "name": "Jane Doe",
            "email": "jane@example.org",
            "message": "",
            "accept_privacy_policy": True,
            "subject": "",
            "ref": "",
            "c0": "AAA",
            "c1": "BBB",
            "c2": "BBBAAA",
        }
    )
    assert not form.is_valid()
    assert "message" in form.errors


def test_blank_name_is_invalid():
    form = ContactForm(
        data={
            "name": "",
            "email": "jane@example.org",
            "message": "I have a question.",
            "accept_privacy_policy": True,
            "subject": "",
            "ref": "",
            "c0": "AAA",
            "c1": "BBB",
            "c2": "BBBAAA",
        }
    )
    assert not form.is_valid()
    assert "name" in form.errors


def test_malformed_email_is_invalid():
    form = ContactForm(
        data={
            "name": "Jane Doe",
            "email": "not-an-email",
            "message": "I have a question.",
            "accept_privacy_policy": True,
            "subject": "",
            "ref": "",
            "c0": "AAA",
            "c1": "BBB",
            "c2": "BBBAAA",
        }
    )
    assert not form.is_valid()
    assert "email" in form.errors


def test_missing_privacy_policy_consent_is_invalid():
    form = ContactForm(
        data={
            "name": "Jane Doe",
            "email": "jane@example.org",
            "message": "I have a question.",
            "accept_privacy_policy": False,
            "subject": "",
            "ref": "",
            "c0": "AAA",
            "c1": "BBB",
            "c2": "BBBAAA",
        }
    )
    assert not form.is_valid()
    assert "accept_privacy_policy" in form.errors


def test_filled_honeypot_is_valid_but_tripped():
    form = ContactForm(
        data={
            "name": "Jane Doe",
            "email": "jane@example.org",
            "message": "I have a question.",
            "accept_privacy_policy": True,
            # The honeypot field is named "subject"; a bot filling it in
            # trips the honeypot.
            "subject": "Buy cheap things",
            "ref": "",
            "c0": "AAA",
            "c1": "BBB",
            "c2": "BBBAAA",
        }
    )
    # The honeypot does not raise a field error ...
    assert form.is_valid(), form.errors
    assert "subject" not in form.errors
    # ... but the form reports that it was tripped.
    assert form.honeypot_tripped is True


def test_unbound_form_seeds_challenge_tokens():
    form = ContactForm()
    c0 = form.fields["c0"].initial
    c1 = form.fields["c1"].initial
    # Fresh tokens are generated for the rendered form.
    assert c0
    assert c1
    assert c0 != c1


def test_challenge_passes_when_c2_matches():
    form = ContactForm(
        data={
            "name": "Jane Doe",
            "email": "jane@example.org",
            "message": "I have a question.",
            "accept_privacy_policy": True,
            "subject": "",
            "ref": "",
            "c0": "AAA",
            "c1": "BBB",
            "c2": "BBBAAA",
        }
    )
    assert form.is_valid(), form.errors
    assert form.challenge_passed is True


@pytest.mark.parametrize(
    "c0,c1,c2",
    [
        # A bot that submits the raw form without running the JS leaves c2
        # empty.
        ("AAA", "BBB", ""),
        # Wrong order (should be c1 + c0).
        ("AAA", "BBB", "AAABBB"),
        # Missing tokens entirely.
        ("", "", ""),
        # Missing first token.
        ("", "BBB", "AAABBB"),
        # Missing second token.
        ("AAA", "", "AAABBB"),
    ],
)
def test_challenge_fails(c0, c1, c2):
    form = ContactForm(
        data={
            "name": "Jane Doe",
            "email": "jane@example.org",
            "message": "I have a question.",
            "accept_privacy_policy": True,
            "subject": "",
            "ref": "",
            "c0": c0,
            "c1": c1,
            "c2": c2,
        }
    )
    assert form.is_valid(), form.errors
    assert form.challenge_passed is False
