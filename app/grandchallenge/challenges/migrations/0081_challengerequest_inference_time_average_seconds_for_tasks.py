from django.db import migrations, models

import grandchallenge.core.validators


def convert_minutes_to_seconds(apps, schema_editor):
    ChallengeRequest = apps.get_model(  # noqa: N806
        "challenges", "ChallengeRequest"
    )
    for challenge_request in ChallengeRequest.objects.exclude(
        inference_time_average_minutes_for_tasks=[]
    ).iterator():
        challenge_request.inference_time_average_seconds_for_tasks = [
            minutes * 60
            for minutes in challenge_request.inference_time_average_minutes_for_tasks
        ]
        challenge_request.save(
            update_fields=["inference_time_average_seconds_for_tasks"]
        )


class Migration(migrations.Migration):

    dependencies = [
        (
            "challenges",
            "0080_alter_challengerequest_average_size_test_case_mb_for_tasks_and_more",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="challengerequest",
            name="inference_time_average_seconds_for_tasks",
            field=models.JSONField(
                default=list,
                help_text="Average run time per algorithm job in seconds, for each task.",
                validators=[
                    grandchallenge.core.validators.JSONValidator(
                        schema={
                            "$schema": "http://json-schema.org/draft-07/schema",
                            "items": {
                                "maximum": 3600,
                                "minimum": 1,
                                "type": "integer",
                            },
                            "type": "array",
                        }
                    )
                ],
            ),
        ),
        migrations.RunPython(
            convert_minutes_to_seconds,
            migrations.RunPython.noop,
        ),
    ]
