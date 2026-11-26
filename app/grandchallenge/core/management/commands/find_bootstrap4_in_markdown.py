import re

from django.apps import apps
from django.core.management import BaseCommand

# Bootstrap 4 only classes/attributes that no longer exist in Bootstrap 5
BOOTSTRAP_4_PATTERN = re.compile(
    r"(?<![\w-])(m[lr]|p[lr])-(sm-|md-|lg-|xl-)?(auto|n?[0-5])\b"
    r"|(?<![\w-])(border-(left|right)|rounded-(left|right)"
    r"|float(-(sm|md|lg|xl))?-(left|right)"
    r"|text(-(sm|md|lg|xl))?-(left|right)"
    r"|dropdown-menu-(left|right)|form-(group|inline|row)"
    r"|custom-(select|control|checkbox|radio|switch|range|file)"
    r"|input-group-(prepend|append)|btn-block"
    r"|badge-(primary|secondary|success|danger|warning|info|light|dark|pill)"
    r"|thead-(light|dark)|card-(columns|deck)|embed-responsive[\w-]*"
    r"|jumbotron|font-weight-\w+|font-italic|text-monospace|sr-only[\w-]*)\b"
    r"|\bdata-(toggle|target|dismiss|ride|spy|slide|slide-to|placement"
    r"|trigger|content|parent|backdrop)="
)

# (app_label.ModelName, field names) for fields rendered as markdown
MARKDOWN_FIELDS = (
    (
        "algorithms.Algorithm",
        (
            "detail_page_markdown",
            "job_create_page_markdown",
            "additional_terms_markdown",
            "summary",
            "mechanism",
            "uses_and_directions",
            "validation_and_performance",
            "warnings",
            "common_error_messages",
            "editor_notes",
        ),
    ),
    ("archives.Archive", ("detail_page_markdown",)),
    (
        "reader_studies.ReaderStudy",
        ("help_text_markdown", "end_of_study_text_markdown", "case_text"),
    ),
    ("challenges.Challenge", ("registration_page_markdown",)),
    ("evaluation.Phase", ("submission_page_markdown",)),
    ("organizations.Organization", ("detail_page_markdown",)),
    ("pages.Page", ("content_markdown",)),
    ("blogs.Post", ("content",)),
    ("documentation.DocPage", ("content",)),
    ("policies.Policy", ("body",)),
    ("emails.Email", ("body",)),
    ("flatpages.FlatPage", ("content",)),
    ("discussion_forums.ForumPost", ("content",)),
    ("components.ComponentInterfaceExampleValue", ("extra_info",)),
)


def _iter_strings(value):
    """Yield all strings in a value, which may be nested JSON (case_text)"""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _iter_strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _iter_strings(v)


class Command(BaseCommand):
    help = (
        "Report markdown fields that contain Bootstrap 4 classes or "
        "data attributes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--hide-matches",
            action="store_true",
            help="Only output the model, field and pk, not the matched text.",
        )

    def handle(self, *args, **options):
        total_objects = 0
        total_fields = 0

        for model_label, field_names in MARKDOWN_FIELDS:
            model = apps.get_model(model_label)

            # One query per model, Python re is used as Postgres regex
            # does not support \b
            for pk, *values in model.objects.values_list(
                "pk", *field_names
            ).iterator(chunk_size=1000):
                field_matches = {}

                for field_name, value in zip(field_names, values, strict=True):
                    matches = {
                        m.group(0)
                        for text in _iter_strings(value)
                        for m in BOOTSTRAP_4_PATTERN.finditer(text)
                    }

                    if matches:
                        field_matches[field_name] = sorted(matches)

                if not field_matches:
                    continue

                total_objects += 1
                total_fields += len(field_matches)

                if options["hide_matches"]:
                    fields = ", ".join(field_matches)
                    self.stdout.write(f"{model_label} pk={pk}: {fields}")
                else:
                    self.stdout.write(f"{model_label} pk={pk}")
                    for field_name, matches in field_matches.items():
                        self.stdout.write(
                            f"    {field_name}: {', '.join(matches)}"
                        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Found matches in {total_fields} field(s) "
                f"across {total_objects} object(s)"
            )
        )
