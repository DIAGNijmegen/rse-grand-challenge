from grandchallenge.contact.forms import ContactForm


class TestContactForm:

    def test_valid_form(self):
        form = ContactForm(
            data={
                "email": "jane@example.org",
                "message": "I have a question.",
            }
        )
        assert form.is_valid(), form.errors

    def test_blank_message_is_invalid(self):
        form = ContactForm(
            data={
                "email": "jane@example.org",
                "message": "",
            }
        )
        assert not form.is_valid()
        assert "message" in form.errors

    def test_malformed_email_is_invalid(self):
        form = ContactForm(
            data={
                "email": "not-an-email",
                "message": "I have a question.",
            }
        )
        assert not form.is_valid()
        assert "email" in form.errors
