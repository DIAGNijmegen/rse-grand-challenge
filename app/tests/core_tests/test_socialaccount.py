import pytest


@pytest.mark.django_db
def test_gmail_login_is_removed(client):
    response = client.get("/accounts/gmail/login/")
    assert response.status_code == 404
