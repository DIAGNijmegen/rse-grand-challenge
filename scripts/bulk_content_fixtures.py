"""
Creates a large amount of content to test how the website renders with
a lot of data (list pages, pagination, leaderboards, long texts, etc.).
"""

import colorsys
import hashlib
import random
import secrets
from datetime import timedelta
from io import BytesIO

from allauth.account.models import EmailAddress
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.flatpages.models import FlatPage
from django.contrib.sites.models import Site
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import transaction
from django.utils.timezone import now
from faker import Faker
from PIL import Image as PILImage
from PIL import ImageOps

from grandchallenge.algorithms.models import (
    Algorithm,
    AlgorithmImage,
    AlgorithmInterface,
    Job,
)
from grandchallenge.anatomy.models import BodyStructure
from grandchallenge.archives.models import Archive, ArchiveItem
from grandchallenge.blogs.models import Post, Tag
from grandchallenge.challenges.models import Challenge, ChallengeSeries
from grandchallenge.components.models import (
    ComponentInterface,
    ComponentInterfaceValue,
)
from grandchallenge.direct_messages.models import Conversation, DirectMessage
from grandchallenge.documentation.models import DocPage
from grandchallenge.evaluation.models import (
    Evaluation,
    Method,
    Phase,
    Submission,
)
from grandchallenge.evaluation.utils import SubmissionKindChoices
from grandchallenge.modalities.models import ImagingModality
from grandchallenge.organizations.models import Organization
from grandchallenge.pages.models import Page
from grandchallenge.reader_studies.models import (
    DisplaySet,
    Question,
    QuestionWidgetKindChoices,
    ReaderStudy,
)
from grandchallenge.task_categories.models import TaskType
from grandchallenge.verifications.models import Verification
from grandchallenge.workstations.models import Workstation
from scripts.development_fixtures import _create_image

PREFIX = "bulk"

COUNTS = {
    "users": 60,
    "organizations": 20,
    "challenges": 60,
    "max_pages_per_challenge": 8,
    "max_phases_per_challenge": 4,
    "max_submissions_per_phase": 40,
    "algorithms": 60,
    "max_jobs_per_algorithm": 6,
    "archives": 40,
    "max_items_per_archive": 25,
    "reader_studies": 40,
    "max_questions_per_reader_study": 6,
    "max_display_sets_per_reader_study": 15,
    "conversations": 30,
    "messages_per_conversation": 25,
    "flatpages": 3,
    "blog_tags": 12,
    "blog_posts": 20,
    "doc_toplevel_pages": 10,
    "max_doc_children_per_page": 3,
    "faq_pages": 10,
}

# Levels of nesting supported by documentation/docpage_detail.html
DOC_PAGE_MAX_DEPTH = 4

fake = Faker()


def run():
    print("📦 Creating bulk content fixtures 📦")

    if not settings.DEBUG:
        raise RuntimeError(
            "Skipping this command, server is not in DEBUG mode."
        )

    _check_not_already_run()

    # Each step has its own transaction so a failure in one of the later
    # steps does not throw away everything that has been created so far.
    users = _create_users()
    organizations = _create_organizations(users)
    _create_extra_taxonomy()
    _create_challenges(users=users, organizations=organizations)
    _create_algorithms(users=users, organizations=organizations)
    _create_archives(users=users, organizations=organizations)
    _create_reader_studies(users=users, organizations=organizations)
    _create_conversations(users)
    _create_flatpages()
    _create_blog_posts(users)
    _create_faq_pages()
    _create_doc_pages()

    print("✨ Bulk content fixtures successfully created ✨")


def _check_not_already_run():
    if Challenge.objects.filter(short_name__startswith=f"{PREFIX}-").exists():
        raise RuntimeError("Bulk content fixtures already created")


# Helpers


# Interesting places in the Mandelbrot set as (x, y, zoom)
MANDELBROT_LOCATIONS = [
    (-0.75, 0.0, 1),
    (-0.7746806106269039, -0.1374168856037867, 1),
    (2.613577e-1, -2.018128e-3, 3.354786e3),
    (-0.59990625, -0.4290703125, 1024),
    (-1.038650e-1, -9.584393e-1, 1.674667e5),
    (-0.761574, -0.0847596, 78125),
    (-1.62917, -0.0203968, 3125),
]


def _mandelbrot_palette():
    """
    A randomized 256 color palette mapping escape time to color, with points
    inside the set (index 0) in black.
    """
    hue_offset = random.random()
    hue_speed = random.uniform(0.5, 3) * random.choice([-1, 1])
    saturation = random.uniform(0.7, 1)

    palette = [0, 0, 0]

    for i in range(1, 256):
        v = i / 255
        r, g, b = colorsys.hsv_to_rgb(
            (hue_offset + v * hue_speed) % 1,
            saturation,
            max(0, 1 - (v - 0.1) ** 2 / 0.9**2),
        )
        palette += [round(r * 255), round(g * 255), round(b * 255)]

    return palette


def _mandelbrot_image(*, size_x, size_y):
    """
    A colored view on a randomly perturbed location, keeping the aspect
    ratio.
    """
    x, y, zoom = random.choice(MANDELBROT_LOCATIONS)

    # Zoom a bit in or out
    zoom *= random.uniform(0.6, 1.6)

    span_y = 3 / zoom
    span_x = span_y * size_x / size_y

    # Pan around the location
    x += random.uniform(-0.25, 0.25) * span_x
    y += random.uniform(-0.25, 0.25) * span_y

    escape_times = PILImage.effect_mandelbrot(
        (size_x, size_y),
        (
            x - span_x / 2,
            y - span_y / 2,
            x + span_x / 2,
            y + span_y / 2,
        ),
        512,
    )
    escape_times.putpalette(_mandelbrot_palette())
    image = escape_times.convert("RGB")

    if random.choice([True, False]):
        image = ImageOps.mirror(image)
    if random.choice([True, False]):
        image = ImageOps.flip(image)

    return image


def _gradient_image(*, size_x, size_y):
    """Blend two random colors using a linear or radial gradient."""
    if random.choice(["linear", "radial"]) == "linear":
        mask = PILImage.linear_gradient("L").rotate(random.choice([0, 90]))
    else:
        mask = PILImage.radial_gradient("L")

    return PILImage.composite(
        PILImage.new(
            "RGB",
            (size_x, size_y),
            tuple(random.randint(0, 255) for _ in range(3)),
        ),
        PILImage.new(
            "RGB",
            (size_x, size_y),
            tuple(random.randint(0, 255) for _ in range(3)),
        ),
        mask.resize((size_x, size_y)),
    )


def _image(*, size_x=256, size_y=None):
    """A randomly generated image so that cards differ."""
    if size_y is None:
        size_y = size_x

    generator = random.choice([_gradient_image, _mandelbrot_image])
    image = generator(size_x=size_x, size_y=size_y)

    io = BytesIO()
    image.save(io, format="JPEG")
    f = InMemoryUploadedFile(io, None, "image.jpeg", "jpeg", io.tell(), None)
    f.seek(0)
    return f


def _banner():
    return _image(size_x=1296, size_y=220)


def _title(words=3):
    return fake.sentence(nb_words=words).rstrip(".").title()


def _long_markdown():
    """Markdown exercising headings, lists, tables, code and links."""
    parts = [f"# {_title(4)}", fake.paragraph(nb_sentences=6)]

    for _ in range(random.randint(2, 5)):
        parts.append(f"## {_title(3)}")
        parts.append("\n\n".join(fake.paragraphs(nb=random.randint(1, 3))))

        kind = random.choice(["list", "table", "code", "quote", "none"])
        if kind == "list":
            parts.append("\n".join(f"- {fake.sentence()}" for _ in range(5)))
        elif kind == "table":
            rows = "\n".join(
                f"| {fake.word()} | {random.randint(1, 1000)} | "
                f"{random.random():.3f} |"
                for _ in range(5)
            )
            parts.append(
                "| Name | Count | Score |\n| --- | --- | --- |\n" + rows
            )
        elif kind == "code":
            parts.append(
                "```python\nimport numpy as np\n\n"
                "def score(prediction, target):\n"
                "    return float(np.mean(prediction == target))\n```"
            )
        elif kind == "quote":
            parts.append(f"> {fake.sentence(nb_words=20)}")

        parts.append(f"See [{fake.word()}]({fake.url()}) for more details.")

    return "\n\n".join(parts)


def _random_sha256():
    return f"sha256:{hashlib.sha256(secrets.token_bytes(32)).hexdigest()}"


def _some(items, low, high):
    items = list(items)
    return random.sample(items, k=min(len(items), random.randint(low, high)))


# Users and organizations


@transaction.atomic
def _create_users():
    print("  👥 Users")
    users = []

    for n in range(COUNTS["users"]):
        username = f"{PREFIX}user{n}"

        user = get_user_model().objects.create(
            username=username,
            email=f"{username}@example.com",
            is_active=True,
            first_name=fake.first_name(),
            last_name=fake.last_name(),
        )
        user.set_password(username)
        user.save()

        EmailAddress.objects.create(
            user=user, email=user.email, verified=True, primary=True
        )
        Verification.objects.create(
            user=user, email=user.email, is_verified=n % 5 != 0
        )

        profile = user.user_profile
        profile.institution = fake.company()
        profile.department = f"Department of {fake.job().title()}s"
        profile.country = fake.country_code()
        profile.receive_newsletter = random.choice([True, False])
        profile.website = fake.url()
        profile.save()

        users.append(user)

    return users


@transaction.atomic
def _create_organizations(users):
    print("  🏢 Organizations")
    organizations = []

    for n in range(COUNTS["organizations"]):
        organization = Organization(
            title=f"{fake.company()} {n}"[:255],
            description=fake.paragraph(nb_sentences=4),
            logo=_image(),
            location=fake.country_code(),
            website=fake.url(),
            detail_page_markdown=_long_markdown(),
        )
        organization.full_clean()
        organization.save()

        for user in _some(users, 1, 6):
            organization.add_editor(user)
            user.groups.add(organization.members_group)

        organizations.append(organization)

    return organizations


@transaction.atomic
def _create_extra_taxonomy():
    print("  🏷 Extra task types and challenge series")

    for task_type in (
        "Detection",
        "Registration",
        "Regression",
        "Survival",
        "Reconstruction",
        "Synthesis",
        "Report Gen.",
        "Quality Check",
    ):
        TaskType.objects.get_or_create(type=task_type)

    for name in ("MICCAI", "ISBI", "SPIE", "MIDL", "RSNA", "ECR", "ESGAR"):
        ChallengeSeries.objects.get_or_create(
            name=name, defaults={"url": fake.url()}
        )

    for modality in ("PET", "OCT", "Fundus", "Ultrasound", "Endoscopy"):
        ImagingModality.objects.get_or_create(modality=modality)


# Challenges


@transaction.atomic
def _create_challenges(*, users, organizations):
    print("  🏆 Challenges, pages, phases, submissions and results")

    task_types = list(TaskType.objects.all())
    modalities = list(ImagingModality.objects.all())
    structures = list(BodyStructure.objects.all())
    series = list(ChallengeSeries.objects.all())

    for n in range(COUNTS["challenges"]):
        hidden = n % 10 == 9
        challenge = Challenge.objects.create(
            short_name=f"{PREFIX}-challenge-{n}",
            title=_title(random.randint(2, 6))[:64],
            description=fake.paragraph(nb_sentences=4)[:1024],
            creator=random.choice(users),
            logo=_image(),
            banner=_banner(),
            hidden=hidden,
            highlight=n % 7 == 0,
            display_forum_link=n % 2 == 0,
            disclaimer=fake.sentence() if n % 8 == 0 else "",
            contact_email=fake.email(),
            event_name=fake.catch_phrase() if n % 2 == 0 else "",
            event_url=fake.url() if n % 2 == 0 else None,
            workshop_date=(
                now().date() + timedelta(days=random.randint(-300, 300))
                if n % 2 == 0
                else None
            ),
            number_of_training_cases=random.choice([None, 20, 150, 4000]),
            number_of_test_cases=random.choice([None, 10, 80, 1200]),
            use_teams=n % 4 == 0,
            registration_page_markdown=_long_markdown() if n % 3 else "",
            data_license_agreement=fake.paragraph(nb_sentences=5),
        )

        # Vary the active state so both active and archived challenges exist
        if n % 6 == 5:
            challenge.is_active_until = now().date() - timedelta(days=30)
        else:
            challenge.is_active_until = now().date() + relativedelta(
                months=random.randint(1, 12)
            )
        challenge.save()

        challenge.task_types.set(_some(task_types, 1, 3))
        challenge.modalities.set(_some(modalities, 1, 3))
        challenge.structures.set(_some(structures, 1, 4))
        challenge.series.set(_some(series, 0, 2))
        challenge.organizations.set(_some(organizations, 0, 3))

        for user in _some(users, 1, 3):
            challenge.add_admin(user)
        for user in _some(users, 5, len(users)):
            challenge.add_participant(user)

        _create_pages(challenge)
        _create_phases(challenge=challenge, users=users)


def _create_pages(challenge):
    permission_levels = [Page.ALL] * 4 + [
        Page.REGISTERED_ONLY,
        Page.ADMIN_ONLY,
    ]

    for _ in range(random.randint(1, COUNTS["max_pages_per_challenge"])):
        Page.objects.create(
            challenge=challenge,
            display_title=_title(random.randint(1, 4))[:255],
            permission_level=random.choice(permission_levels),
            hidden=random.random() < 0.1,
            content_markdown=_long_markdown(),
        )


def _create_phases(*, challenge, users):
    for p in range(random.randint(1, COUNTS["max_phases_per_challenge"])):
        phase_name = random.choice(
            ["Preliminary", "Final", "Open", "Validation", "Test"]
        )
        phase = Phase.objects.create(
            challenge=challenge,
            title=f"{phase_name} {p + 1}",
            submission_kind=SubmissionKindChoices.CSV,
            score_title="Accuracy ± std",
            score_jsonpath="acc.mean",
            score_error_jsonpath="acc.std",
            score_decimal_places=random.choice([2, 3, 4]),
            extra_results_columns=[
                {
                    "title": "Dice ± std",
                    "path": "dice.mean",
                    "error_path": "dice.std",
                    "order": "desc",
                }
            ],
            submissions_limit_per_user_per_period=random.choice([1, 5, 10]),
            submissions_open_at=now() - timedelta(days=random.randint(1, 200)),
            submissions_close_at=(
                now() + timedelta(days=random.randint(-50, 200))
                if p % 2
                else None
            ),
        )

        method = Method.objects.create(
            creator=challenge.creator,
            phase=phase,
            image_sha256=_random_sha256(),
            import_status=Method.ImportStatusChoices.COMPLETED,
            is_manifest_valid=True,
            is_in_registry=True,
            is_desired_version=True,
        )

        _create_results(
            phase=phase, method=method, challenge=challenge, users=users
        )


def _create_results(*, phase, method, challenge, users):
    """Create submissions with evaluations so leaderboards are populated."""
    interface = ComponentInterface.objects.get(slug="metrics-json-file")
    participants = list(challenge.participants_group.user_set.all()) or users

    for _ in range(random.randint(0, COUNTS["max_submissions_per_phase"])):
        submission = Submission(
            phase=phase,
            creator=random.choice(participants),
            algorithm_requires_gpu_type="",
            algorithm_requires_memory_gb=0,
        )
        submission.predictions_file.save(
            "predictions.csv", ContentFile(b"case,value\n")
        )
        submission.save()

        evaluation = Evaluation.objects.create(
            submission=submission,
            method=method,
            status=random.choices(
                [
                    Evaluation.SUCCESS,
                    Evaluation.FAILURE,
                    Evaluation.CANCELLED,
                ],
                weights=[8, 1, 1],
            )[0],
            time_limit=phase.evaluation_time_limit,
            requires_gpu_type=phase.evaluation_requires_gpu_type,
            requires_memory_gb=phase.evaluation_requires_memory_gb,
        )

        if evaluation.status == Evaluation.SUCCESS:
            civ = ComponentInterfaceValue.objects.create(
                interface=interface,
                value={
                    "acc": {
                        "mean": round(random.random(), 4),
                        "std": round(random.random() / 5, 4),
                    },
                    "dice": {
                        "mean": round(random.random(), 4),
                        "std": round(random.random() / 5, 4),
                    },
                },
            )
            evaluation.outputs.add(civ)


# Algorithms


@transaction.atomic
def _create_algorithms(*, users, organizations):
    print("  🤖 Algorithms, images and jobs")

    modalities = list(ImagingModality.objects.all())
    structures = list(BodyStructure.objects.all())

    input_interface = ComponentInterface.objects.get(
        slug="generic-medical-image"
    )
    output_interface = ComponentInterface.objects.get(slug="results-json-file")
    interface = AlgorithmInterface.objects.create(
        inputs=[input_interface], outputs=[output_interface]
    )

    input_civ = ComponentInterfaceValue.objects.create(
        interface=input_interface,
        image=_create_image(name="bulk_input.mha", width=10, height=10),
    )

    for n in range(COUNTS["algorithms"]):
        algorithm = Algorithm.objects.create(
            title=f"{PREFIX.title()} Algorithm {n}: {_title(3)}"[:255],
            description=fake.paragraph(nb_sentences=3),
            summary=fake.paragraph(nb_sentences=5),
            logo=_image(),
            public=n % 4 != 0,
            highlight=n % 9 == 0,
            contact_email=fake.email(),
            display_editors=n % 2 == 0,
            detail_page_markdown=_long_markdown(),
            job_create_page_markdown=_long_markdown() if n % 3 == 0 else "",
            repo_name=f"github-username/{PREFIX}-repo-{n}" if n % 2 else "",
        )
        algorithm.interfaces.set([interface])
        algorithm.modalities.set(_some(modalities, 1, 3))
        algorithm.structures.set(_some(structures, 1, 3))
        algorithm.organizations.set(_some(organizations, 0, 2))

        for user in _some(users, 1, 3):
            algorithm.add_editor(user)
        for user in _some(users, 0, 15):
            algorithm.add_user(user)

        image = AlgorithmImage.objects.create(
            creator=random.choice(users),
            algorithm=algorithm,
            image_sha256=_random_sha256(),
            import_status=AlgorithmImage.ImportStatusChoices.COMPLETED,
            is_manifest_valid=True,
            is_in_registry=True,
            is_desired_version=True,
        )

        for _ in range(random.randint(0, COUNTS["max_jobs_per_algorithm"])):
            job = Job.objects.create(
                creator=random.choice(users),
                algorithm_image=image,
                algorithm_interface=interface,
                status=random.choice(
                    [Job.SUCCESS] * 6 + [Job.FAILURE, Job.CANCELLED]
                ),
                time_limit=60,
                requires_gpu_type=algorithm.job_requires_gpu_type,
                requires_memory_gb=algorithm.job_requires_memory_gb,
            )
            job.inputs.add(input_civ)
            job.outputs.add(
                ComponentInterfaceValue.objects.create(
                    interface=output_interface,
                    value={"score": round(random.random(), 3)},
                )
            )


# Archives


@transaction.atomic
def _create_archives(*, users, organizations):
    print("  🗄 Archives and items")

    workstation = Workstation.objects.get(
        slug=settings.DEFAULT_WORKSTATION_SLUG
    )
    modalities = list(ImagingModality.objects.all())
    structures = list(BodyStructure.objects.all())
    interface = ComponentInterface.objects.get(slug="generic-medical-image")

    for n in range(COUNTS["archives"]):
        archive = Archive.objects.create(
            title=f"{PREFIX.title()} Archive {n}: {_title(3)}"[:255],
            description=fake.paragraph(nb_sentences=3),
            detail_page_markdown=_long_markdown(),
            logo=_image(),
            workstation=workstation,
            public=n % 3 == 0,
        )
        archive.modalities.set(_some(modalities, 1, 3))
        archive.structures.set(_some(structures, 1, 3))
        archive.organizations.set(_some(organizations, 0, 2))

        for user in _some(users, 1, 3):
            archive.add_editor(user)
        for user in _some(users, 0, 5):
            archive.add_uploader(user)
        for user in _some(users, 0, 10):
            archive.add_user(user)

        for i in range(random.randint(0, COUNTS["max_items_per_archive"])):
            item = ArchiveItem.objects.create(
                archive=archive, title=f"Case {i}"
            )
            item.values.add(
                ComponentInterfaceValue.objects.create(
                    interface=interface,
                    image=_create_image(
                        name=f"bulk_archive_{n}_{i}.mha",
                        width=10,
                        height=10,
                    ),
                )
            )


# Reader studies


@transaction.atomic
def _create_reader_studies(*, users, organizations):
    print("  📖 Reader studies, questions and display sets")

    workstation = Workstation.objects.get(
        slug=settings.DEFAULT_WORKSTATION_SLUG
    )
    modalities = list(ImagingModality.objects.all())
    structures = list(BodyStructure.objects.all())
    interface = ComponentInterface.objects.get(slug="generic-medical-image")

    question_types = [
        (Question.AnswerType.TEXT, QuestionWidgetKindChoices.TEXT_INPUT),
        (Question.AnswerType.TEXT, QuestionWidgetKindChoices.TEXT_AREA),
        (Question.AnswerType.BOOL, ""),
        (Question.AnswerType.NUMBER, QuestionWidgetKindChoices.NUMBER_INPUT),
    ]

    for n in range(COUNTS["reader_studies"]):
        reader_study = ReaderStudy.objects.create(
            title=f"{PREFIX.title()} Reader Study {n}: {_title(3)}"[:255],
            description=fake.paragraph(nb_sentences=3),
            logo=_image(),
            workstation=workstation,
            public=n % 3 == 0,
            view_content={"main": ["generic-medical-image"]},
            max_credits=5000,
        )
        reader_study.modalities.set(_some(modalities, 1, 3))
        reader_study.structures.set(_some(structures, 1, 3))
        reader_study.organizations.set(_some(organizations, 0, 2))

        for user in _some(users, 1, 3):
            reader_study.add_editor(user)
        for user in _some(users, 0, 15):
            reader_study.add_reader(user)

        for q in range(
            random.randint(1, COUNTS["max_questions_per_reader_study"])
        ):
            answer_type, widget = random.choice(question_types)
            Question.objects.create(
                reader_study=reader_study,
                question_text=f"{_title(6)}?",
                answer_type=answer_type,
                widget=widget,
                order=q,
            )

        for _ in range(
            random.randint(0, COUNTS["max_display_sets_per_reader_study"])
        ):
            display_set = DisplaySet.objects.create(reader_study=reader_study)
            display_set.values.set(
                [
                    ComponentInterfaceValue.objects.create(
                        interface=interface,
                        image=_create_image(
                            name=f"bulk_rs_{n}.mha", width=10, height=10
                        ),
                    )
                ]
            )


# Direct messages


@transaction.atomic
def _create_conversations(users):
    print("  💬 Direct messages")

    for _ in range(COUNTS["conversations"]):
        participants = random.sample(users, k=random.randint(2, 4))
        conversation = Conversation.objects.create()
        conversation.participants.set(participants)

        unread = random.choice([True, False])

        for _ in range(random.randint(1, COUNTS["messages_per_conversation"])):
            sender = random.choice(participants)
            message = DirectMessage.objects.create(
                conversation=conversation,
                sender=sender,
                message=fake.text(max_nb_chars=random.choice([60, 160, 600])),
            )
            if unread:
                message.unread_by.set(set(participants) - {sender})


# Flatpages


@transaction.atomic
def _create_flatpages():
    print("  📄 Flatpages")
    site = Site.objects.get(pk=settings.SITE_ID)

    for n in range(COUNTS["flatpages"]):
        page = FlatPage.objects.create(
            url=f"/{PREFIX}-flatpage-{n}/",
            title=_title(random.randint(1, 4)),
            content=_long_markdown(),
            registration_required=n % 5 == 4,
        )
        page.sites.add(site)


# Blog posts


@transaction.atomic
def _create_blog_posts(users):
    print("  📰 Blog posts and tags")

    tags = [
        Tag.objects.get_or_create(name=f"{PREFIX}-{fake.word()}-{n}")[0]
        for n in range(COUNTS["blog_tags"])
    ]

    for n in range(COUNTS["blog_posts"]):
        post = Post.objects.create(
            title=f"{_title(random.randint(3, 8))}"[:1024],
            description=fake.paragraph(nb_sentences=3),
            content=_long_markdown(),
            logo=_image(size_x=400, size_y=300),
            published=n % 5 != 4,
            highlight=n % 10 == 0,
        )
        post.tags.set(_some(tags, 0, 4))

        for user in _some(users, 1, 3):
            post.add_author(user)

        # created is auto_now_add so spread the dates out afterwards
        Post.objects.filter(pk=post.pk).update(
            created=now() - timedelta(days=random.randint(0, 700))
        )


# Documentation pages


def _create_doc_page_tree(*, parent, depth):
    page = DocPage.objects.create(
        title=_title(random.randint(2, 4)),
        content=_long_markdown(),
        parent=parent,
    )

    if depth < DOC_PAGE_MAX_DEPTH:
        for _ in range(random.randint(0, COUNTS["max_doc_children_per_page"])):
            _create_doc_page_tree(parent=page, depth=depth + 1)


@transaction.atomic
def _create_doc_pages():
    print("  📚 Documentation pages")

    for _ in range(COUNTS["doc_toplevel_pages"]):
        _create_doc_page_tree(parent=None, depth=1)


@transaction.atomic
def _create_faq_pages():
    print("  📚 FAQ pages")

    faq = DocPage.objects.create(title="FAQ", content="", is_faq=True)
    for category in [
        "Challenge",
        "Algorithms",
        "Reader Studies",
        "Data",
        "Security",
        "Invoices",
    ]:
        parent = DocPage.objects.create(
            title=category,
            content="",
            is_faq=True,
            parent=faq,
        )

        for _ in range(COUNTS["faq_pages"]):
            DocPage.objects.create(
                title=f"{_title(10)}?",
                content=_long_markdown(),
                is_faq=True,
                parent=parent,
            )
