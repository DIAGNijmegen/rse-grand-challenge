import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "challenges",
            "0061_alter_challenge_banner_alter_challenge_logo_and_more",
        ),
    ]

    operations = [
        migrations.RenameField(
            model_name="challengerequest",
            old_name="average_size_of_test_image_in_mb",
            new_name="average_size_of_test_case_in_mb",
        ),
        migrations.RenameField(
            model_name="challengerequest",
            old_name="phase_1_number_of_test_images",
            new_name="phase_1_number_of_test_cases",
        ),
        migrations.RenameField(
            model_name="challengerequest",
            old_name="phase_2_number_of_test_images",
            new_name="phase_2_number_of_test_cases",
        ),
        migrations.AlterField(
            model_name="challengerequest",
            name="algorithm_inputs",
            field=models.TextField(
                help_text="What are the inputs to the algorithms submitted as solutions to your challenge going to be? Please describe in detail what the input(s) reflect(s), for example, MRI scan of the brain, or chest X-ray."
            ),
        ),
        migrations.AlterField(
            model_name="challengerequest",
            name="algorithm_outputs",
            field=models.TextField(
                help_text="What are the outputs to the algorithms submitted as solutions to your challenge going to be? Please describe in detail what the output(s) reflect(s), for example, probability of a positive PCR result, or stroke lesion segmentation."
            ),
        ),
        migrations.AlterField(
            model_name="challengerequest",
            name="average_size_of_test_case_in_mb",
            field=models.PositiveIntegerField(
                help_text="Average size of a test case in MB.",
                validators=[
                    django.core.validators.MinValueValidator(limit_value=1),
                    django.core.validators.MaxValueValidator(
                        limit_value=10000
                    ),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="challengerequest",
            name="phase_1_number_of_test_cases",
            field=models.PositiveIntegerField(
                help_text="Number of test cases for this phase."
            ),
        ),
        migrations.AlterField(
            model_name="challengerequest",
            name="phase_2_number_of_test_cases",
            field=models.PositiveIntegerField(
                help_text="Number of test cases for this phase."
            ),
        ),
        migrations.AddField(
            model_name="challengerequest",
            name="average_size_of_prediction_in_mb",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Average size of prediction output per test case in MB.",
                validators=[
                    django.core.validators.MaxValueValidator(limit_value=10000)
                ],
            ),
            preserve_default=False,
        ),
    ]
