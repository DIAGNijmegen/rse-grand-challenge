import zoneinfo

import pytest


def test_legacy_alias_resolves():
    # Legacy IANA aliases such as "Asia/Calcutta" were dropped from Debian
    # trixie's system tzdata. The "tzdata" dependency restores them via
    # zoneinfo's PyPI fallback, so they must continue to resolve.
    assert zoneinfo.ZoneInfo("Asia/Calcutta").key == "Asia/Calcutta"
    assert "Asia/Calcutta" in zoneinfo.available_timezones()


@pytest.mark.django_db
def test_session_with_legacy_alias_does_not_crash(client):
    # A session that stored a legacy alias (e.g. under an older OS) must
    # still be activatable by the timezone middleware.
    session = client.session
    session["timezone"] = "Asia/Calcutta"
    session.save()

    response = client.get(path="/")

    assert response.status_code == 200
    assert response.context[-1]["TIME_ZONE"] == "Asia/Calcutta"
