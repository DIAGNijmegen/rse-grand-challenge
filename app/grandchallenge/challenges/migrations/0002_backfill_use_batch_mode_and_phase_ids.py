from django.db import migrations


def backfill_phase_fields(apps, schema_editor):
    ChallengeRequest = apps.get_model(  # noqa: N806
        "challenges", "ChallengeRequest"
    )

    requests_to_update = []

    for challenge_request in ChallengeRequest.objects.all():
        number_of_phases = len(challenge_request.task_id_for_phases)

        changed = False

        if (
            number_of_phases
            and not challenge_request.use_batch_mode_for_phases
        ):
            challenge_request.use_batch_mode_for_phases = [
                False
            ] * number_of_phases
            changed = True

        if number_of_phases and not challenge_request.phase_ids:
            challenge_request.phase_ids = list(range(1, number_of_phases + 1))
            changed = True

        if changed:
            requests_to_update.append(challenge_request)

    if requests_to_update:
        ChallengeRequest.objects.bulk_update(
            requests_to_update,
            ["use_batch_mode_for_phases", "phase_ids"],
        )


class Migration(migrations.Migration):

    dependencies = [
        (
            "challenges",
            "0001_squashed_0082_challengerequest_phase_ids_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(
            code=backfill_phase_fields,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
