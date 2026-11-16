import time

import pytest
from django.contrib.auth.models import Group
from django.db import connection
from django.test.utils import CaptureQueriesContext
from knox.auth import TokenAuthentication
from knox.models import AuthToken

from grandchallenge.uploads.models import UserUpload
from tests.factories import UserFactory

NUMBER_OF_GROUPS = 70_000


def _add_user_to_many_groups(*, user, number_of_groups):
    """Create ``number_of_groups`` groups and add ``user`` to all of them.

    Uses bulk inserts on the Group table and the user/group through table so
    that building the fixture itself does not dominate the test runtime.
    """
    groups = Group.objects.bulk_create(
        [
            Group(name=f"perf_test_group_{index:06}")
            for index in range(number_of_groups)
        ],
        batch_size=5_000,
    )

    through_model = user.groups.through
    through_model.objects.bulk_create(
        [
            through_model(user_id=user.pk, group_id=group.pk)
            for group in groups
        ],
        batch_size=5_000,
    )

    return groups


def _generate_presigned_urls_via_api(*, client, token, upload):
    """Call the "get signed urls to upload chunks" detail endpoint.

    This is a detail action, so it runs ``get_object()`` which applies
    ``ViewObjectPermissionsFilter`` -> ``filter_by_permission`` -- the code
    path that materialises the user's group pks and builds a ``group_pk__in``
    clause.
    """
    return client.patch(
        f"/api/v1/uploads/{upload.pk}/{upload.s3_upload_id}/"
        "generate-presigned-urls/",
        data={"part_numbers": [1]},
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )


@pytest.mark.django_db
def test_presigned_urls_does_not_run_group_filter_for_user_only_uploads(
    client,
):
    """Guard the fix for the reported ~4s auth slowdown.

    The report blamed "Knox auth", but:

    1. Knox token authentication is a primary-key lookup on the hashed token
       and is cheap regardless of how many groups the user belongs to.
    2. The slowdown surfaced on *detail* endpoints such as
       "generate-presigned-urls" (used to get signed URLs to upload chunks).
       These call ``get_object()``, which runs
       ``grandchallenge.core.guardian.filter_by_permission``.

    UserUpload object permissions are only ever assigned to the creator
    *user* (see ``UserUpload.assign_permissions`` and
    ``UserUploadGroupObjectPermission.allowed_permissions == frozenset()``),
    so the group branch of ``filter_by_permission`` is never needed. The fix
    makes ``filter_by_permission`` evaluate the user's group pks lazily, so
    for a user-only model like UserUpload it no longer issues a
    ``group_pk__in=<all the user's groups>`` query.

    This test asserts that, even for a user in 70,000 groups, the
    presigned-urls request does not run that group-pk query against the
    UserUpload group-permission table, Knox stays fast, and the query count
    does not scale with group count.
    """
    # Warm up application-level caches (boto clients, content types, etc.) so
    # first-request overhead does not pollute the measurements.
    warmup_user = UserFactory()
    _, warmup_token = AuthToken.objects.create(user=warmup_user, expiry=None)
    warmup_upload = UserUpload.objects.create(creator=warmup_user)
    assert (
        _generate_presigned_urls_via_api(
            client=client, token=warmup_token, upload=warmup_upload
        ).status_code
        == 200
    )

    baseline_user = UserFactory()
    _, baseline_token = AuthToken.objects.create(
        user=baseline_user, expiry=None
    )
    baseline_upload = UserUpload.objects.create(creator=baseline_user)

    many_groups_user = UserFactory()
    _, many_groups_token = AuthToken.objects.create(
        user=many_groups_user, expiry=None
    )
    many_groups_upload = UserUpload.objects.create(creator=many_groups_user)

    _add_user_to_many_groups(
        user=many_groups_user, number_of_groups=NUMBER_OF_GROUPS
    )
    assert many_groups_user.groups.count() >= NUMBER_OF_GROUPS

    # 1. The pure Knox token authentication step for the many-groups user.
    knox_auth_start = time.perf_counter()
    authenticated_user, _ = TokenAuthentication().authenticate_credentials(
        many_groups_token
    )
    knox_auth_seconds = time.perf_counter() - knox_auth_start
    assert authenticated_user == many_groups_user

    # 2. Baseline detail request for a user with no extra groups, capturing
    #    the SQL so we can compare the query count against the many-groups
    #    request.
    with CaptureQueriesContext(connection) as baseline_queries:
        baseline_start = time.perf_counter()
        baseline_response = _generate_presigned_urls_via_api(
            client=client, token=baseline_token, upload=baseline_upload
        )
        baseline_seconds = time.perf_counter() - baseline_start
    assert baseline_response.status_code == 200

    # 3. Detail request for the user with 70,000 groups, capturing the SQL so
    #    we can confirm no group-pk query runs against the UserUpload
    #    group-permission table.
    with CaptureQueriesContext(connection) as captured_queries:
        many_groups_start = time.perf_counter()
        many_groups_response = _generate_presigned_urls_via_api(
            client=client,
            token=many_groups_token,
            upload=many_groups_upload,
        )
        many_groups_seconds = time.perf_counter() - many_groups_start
    assert many_groups_response.status_code == 200

    slowdown_factor = many_groups_seconds / baseline_seconds

    baseline_query_count = len(baseline_queries.captured_queries)
    many_groups_query_count = len(captured_queries.captured_queries)
    query_count_increase = many_groups_query_count - baseline_query_count

    # The pathology we fixed lived in filter_by_permission: it used to
    # evaluate ``{*user.groups.values_list("pk", flat=True)}`` -- i.e. select
    # every group the user belongs to by joining auth_user_groups -- and then
    # embed those pks as a literal ``group_pk__in`` list. That standalone
    # "fetch all my group pks" query is the thing that is slow for a user in
    # 70,000 groups.
    #
    # We detect it as a SELECT from auth_group that joins auth_user_groups.
    # This is distinct from:
    #   * Django's ModelBackend model-permission join (auth_group_permissions),
    #   * guardian's object-permission checker, which uses an IN (SELECT ...)
    #     subquery rather than materialising the pks in Python.
    def is_group_pk_materialisation(sql):
        normalised = sql.lower()
        return (
            'from "auth_group"' in normalised
            and "auth_user_groups" in normalised
            and " in (select" not in normalised
        )

    group_pk_materialisation_queries = [
        query
        for query in captured_queries.captured_queries
        if is_group_pk_materialisation(query["sql"])
    ]

    slowest_queries = sorted(
        captured_queries.captured_queries,
        key=lambda query: float(query["time"]),
        reverse=True,
    )[:5]
    slowest_report = "\n".join(
        f"  {query['time']}s  {query['sql'][:160]}"
        for query in slowest_queries
    )

    print(
        f"\nKnox token authentication:          {knox_auth_seconds:.4f}s"
        f"\nBaseline presigned-urls (0 groups): {baseline_seconds:.4f}s"
        f"\nPresigned-urls ({NUMBER_OF_GROUPS} groups):  "
        f"{many_groups_seconds:.4f}s"
        f"\nSlowdown factor:                    {slowdown_factor:.1f}x"
        f"\nBaseline query count:               {baseline_query_count}"
        f"\nMany-groups query count:            {many_groups_query_count}"
        f"\nQuery count increase:               {query_count_increase}"
        f"\nSlowest queries:\n{slowest_report}"
    )

    # The Knox token step is a primary-key lookup and stays fast even with
    # 70,000 groups -- it is not the source of the slowdown.
    assert knox_auth_seconds < baseline_seconds, (
        "Knox token authentication was unexpectedly slow "
        f"({knox_auth_seconds:.4f}s); the slowdown is not in the token "
        "lookup."
    )

    # The fix: filter_by_permission no longer materialises the user's group
    # pks for UserUpload. The view sets only_consider_user_permissions=True,
    # and filter_by_permission evaluates the group pks lazily, so the group
    # branch -- and its "fetch all my group pks" query -- is skipped entirely.
    assert not group_pk_materialisation_queries, (
        "filter_by_permission materialised the user's group pks (a SELECT "
        "from auth_group joined to auth_user_groups) even though UserUpload "
        "only has user object permissions. This query is slow for users in a "
        "large number of groups and must be skipped. Offending SQL: "
        f"{[q['sql'] for q in group_pk_materialisation_queries]}"
    )

    # The *number* of queries does not scale with the number of groups.
    assert query_count_increase <= 1, (
        "Expected the query count to stay roughly constant regardless of "
        f"group count, but it increased by {query_count_increase} "
        f"(baseline {baseline_query_count}, "
        f"many-groups {many_groups_query_count})."
    )
