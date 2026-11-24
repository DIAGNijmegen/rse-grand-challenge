from django.db import migrations, models


def migrate_allow_submission_comments(apps, schema_editor):
    Phase = apps.get_model("evaluation", "Phase")  # noqa: N806
    Phase.objects.filter(allow_submission_comments=True).update(
        submission_comments_choice="opt"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("evaluation", "0121_batchjobtask_evaluation__parsing_a83107_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="phase",
            name="submission_comments_choice",
            field=models.CharField(
                choices=[
                    ("off", "Off"),
                    ("opt", "Optional"),
                    ("req", "Required"),
                ],
                default="off",
                help_text="Show a comment field on the submission page so that users can add a comment to their submission. Off turns this feature off, Optional means that including a comment is optional for the user, Required means that the user must provide a comment.",
                max_length=3,
            ),
        ),
        migrations.AddField(
            model_name="phase",
            name="submission_comments_label",
            field=models.CharField(
                blank=True,
                default="Comment",
                help_text="The label that will be used on the submission and results page for the comment. For example: Method Description.",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="phase",
            name="submission_comments_help_text",
            field=models.CharField(
                blank=True,
                default="",
                help_text='The help text to include on the submissions page to describe the comment. Eg: "A short description of your method.".',
                max_length=128,
            ),
        ),
        migrations.RunPython(
            migrate_allow_submission_comments,
            migrations.RunPython.noop,
            elidable=True,
        ),
        migrations.RemoveField(
            model_name="phase",
            name="allow_submission_comments",
        ),
        migrations.AddConstraint(
            model_name="phase",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("submission_comments_choice__in", ["off", "opt", "req"])
                ),
                name="evaluation_phase_submission_comments_choice_valid",
            ),
        ),
    ]
