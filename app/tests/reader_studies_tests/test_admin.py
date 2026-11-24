from django.contrib import admin

from grandchallenge.reader_studies.admin import ReaderStudyAdmin
from grandchallenge.reader_studies.models import ReaderStudy


def test_credits_consumed_display_uncalculated_without_max_credits():
    reader_study = ReaderStudy(max_credits=None, credits_consumed=None)
    reader_study_admin = ReaderStudyAdmin(ReaderStudy, admin.site)

    assert (
        reader_study_admin.credits_consumed_display(reader_study)
        == "Uncalculated (no max credits set)"
    )


def test_credits_consumed_display_updating_when_null_with_max_credits():
    reader_study = ReaderStudy(max_credits=1000, credits_consumed=None)
    reader_study_admin = ReaderStudyAdmin(ReaderStudy, admin.site)

    assert (
        reader_study_admin.credits_consumed_display(reader_study) == "Updating"
    )


def test_credits_consumed_display_shows_value():
    reader_study = ReaderStudy(credits_consumed=500)
    reader_study_admin = ReaderStudyAdmin(ReaderStudy, admin.site)

    assert reader_study_admin.credits_consumed_display(reader_study) == 500
