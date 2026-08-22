from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from vendors.models import Client, ClientIntegration

from .models import Survey, SurveyAttempt, SurveyQuota, TargetingQuestion
from .outcomes import provider_outcome
from .providers.rmwinsights import RMWInsightsProvider
from .serializers import SurveyQuotaSerializer, TargetingQuestionSerializer


def remote_row(**overrides):
    row = {
        "id": 2961,
        "local_id": "20260800002961",
        "survey_id": "16120319",
        "client_name": "InnovateMR",
        "display_company_name": "InnovateMR",
        "name": "Consumer research",
        "status": "live",
        "sample_size": 175,
        "completes": 5,
        "remaining": 170,
        "starts": 12,
        "cpi": "2.45",
        "loi": 15,
        "incidence_rate": "35.00",
        "country": "United States",
        "country_code": "",
        "language": "English",
        "language_code": "EN",
        "survey_type": "B2C",
        "supplier_entry_link": (
            "https://api.rmwinsights.com/supplier/start?key=key-id"
            "&survey=20260800002961&token=signed-token&pid=[%%pid%%]"
        ),
        "has_quota": True,
        "source_created_at": "2026-08-20T08:00:00Z",
        "source_modified_at": "2026-08-21T09:30:00Z",
    }
    row.update(overrides)
    return row


class RMWInsightsProviderTests(SimpleTestCase):
    def integration(self):
        return SimpleNamespace(
            base_url="https://api.rmwinsights.com/api/v1/surveys/",
            config={"page_size": 100, "max_pages": 10},
        )

    @patch("surveys.providers.rmwinsights.resolve_integration_token", return_value="secret")
    def test_inventory_fetches_every_drf_page(self, _token):
        first = Mock()
        first.raise_for_status.return_value = None
        first.json.return_value = {"count": 2, "next": "remote-next", "results": [remote_row()]}
        second = Mock()
        second.raise_for_status.return_value = None
        second.json.return_value = {
            "count": 2,
            "next": None,
            "results": [remote_row(local_id="20260800002962", survey_id="16120320")],
        }
        session = Mock()
        session.get.side_effect = [first, second]

        rows = RMWInsightsProvider(self.integration(), session=session).inventory()

        self.assertEqual(len(rows), 2)
        self.assertEqual(session.get.call_count, 2)
        self.assertEqual(session.get.call_args_list[0].kwargs["params"]["page"], 1)
        self.assertEqual(session.get.call_args_list[1].kwargs["params"]["page"], 2)
        self.assertEqual(session.get.call_args_list[0].kwargs["headers"]["X-API-Key"], "secret")

    @patch("surveys.providers.rmwinsights.resolve_integration_token", return_value="secret")
    def test_normalization_maps_remote_project_and_country(self, _token):
        provider = RMWInsightsProvider(self.integration(), session=Mock())

        normalized = provider.normalize_inventory_item(remote_row(), timezone.now())

        self.assertEqual(normalized.source_key, "16120319")
        self.assertEqual(normalized.numeric_source_id, 16120319)
        self.assertEqual(normalized.raw_data["remote_project_id"], "20260800002961")
        self.assertEqual(normalized.values["country"], "United States")
        self.assertEqual(normalized.values["country_code"], "US")
        self.assertEqual(normalized.values["survey_type"], "B2C")
        self.assertEqual(str(normalized.values["cpi"]), "2.45")
        self.assertIn("pid=[%%pid%%]", normalized.values["entry_link"])

    @patch("surveys.providers.rmwinsights.resolve_integration_token", return_value="secret")
    def test_outbound_link_replaces_only_remote_pid(self, _token):
        provider = RMWInsightsProvider(self.integration(), session=Mock())
        survey = SimpleNamespace(entry_link=remote_row()["supplier_entry_link"])

        outbound = provider.build_outbound_url(
            survey,
            SimpleNamespace(rid="Ab3De6Gh9J", pid="Px7Qa2B"),
            {"ignored": "answer"},
        )
        query = parse_qs(urlsplit(outbound).query)

        self.assertEqual(query["pid"], ["Px7Qa2B"])
        self.assertEqual(query["key"], ["key-id"])
        self.assertEqual(query["token"], ["signed-token"])
        self.assertEqual(query["survey"], ["20260800002961"])

    @patch("surveys.providers.rmwinsights.resolve_integration_token", return_value="secret")
    def test_remote_attempt_uses_authenticated_attempt_detail_endpoint(self, _token):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"rid": "lGmOI3Sfo3", "status": "4"}
        session = Mock()
        session.get.return_value = response

        payload = RMWInsightsProvider(self.integration(), session=session).remote_attempt(
            "lGmOI3Sfo3"
        )

        self.assertEqual(payload["status"], "4")
        self.assertEqual(
            session.get.call_args.args[0],
            "https://api.rmwinsights.com/api/v1/survey-attempts/lGmOI3Sfo3/",
        )
        self.assertEqual(session.get.call_args.kwargs["headers"]["X-API-Key"], "secret")


class RMWInsightsDetailsTests(TestCase):
    def setUp(self):
        self.client_record = Client.objects.create(
            code="rmw-details", name="InnovateMR", provider_code="innovatemr"
        )
        self.detail_integration = ClientIntegration.objects.create(
            client=self.client_record,
            name="Legacy Innovate details",
            provider_code="innovatemr",
            base_url="https://supplier.innovatemr.net/api/v2",
        )
        self.integration = ClientIntegration.objects.create(
            client=self.client_record,
            name="RMW live",
            provider_code="rmwinsights",
            base_url="https://api.rmwinsights.com/api/v1/surveys/",
            config={"detail_integration_id": self.detail_integration.pk},
        )
        self.survey = Survey.objects.create(
            client=self.client_record,
            integration=self.integration,
            source_key="20260800002961",
            source_id=16120319,
            name="Remote survey",
            entry_link=remote_row()["supplier_entry_link"],
            raw_data={"remote_project_id": "20260800002961"},
        )

    @patch("surveys.providers.rmwinsights.resolve_integration_token", return_value="secret")
    def test_live_detail_client_uses_configured_legacy_innovate_integration(self, _token):
        provider = RMWInsightsProvider(self.integration, session=Mock())

        detail_client = provider._innovate_client()

        self.assertEqual(detail_client.integration, self.detail_integration)
        self.assertEqual(detail_client.provider_code, "innovatemr")

    @patch("surveys.providers.rmwinsights.resolve_integration_token", return_value="secret")
    def test_refresh_details_uses_legacy_innovate_api_and_preserves_rmw_link(self, _token):
        detail_client = Mock()
        detail_client.is_biobrain = False
        detail_client.get_quota_for_survey.return_value = [{
            "_id": "quota-9001", "id": 9001, "quotaName": "Total",
            "quotaN": 175, "RemainingN": 170, "cmp": 5, "clk": 12,
            "quotaStatus": "Open", "targeting": {
                "GENDER": [{"OptionId": 2, "OptionText": "Female"}],
            },
        }]
        detail_client.get_survey_targeting.return_value = [{
            "QuestionId": 59, "QuestionKey": "GENDER",
            "QuestionText": "What is your gender?", "QuestionType": "single",
            "QuestionCategory": "Profile", "Options": [
                {"OptionId": "1", "OptionText": "Male"},
            ],
        }]
        original_link = self.survey.entry_link

        RMWInsightsProvider(
            self.integration,
            session=Mock(),
            detail_client=detail_client,
        ).refresh_details(self.survey)

        self.survey.refresh_from_db()
        self.assertEqual(self.survey.quotas.count(), 1)
        self.assertEqual(self.survey.targeting_questions.count(), 1)
        question = self.survey.targeting_questions.get()
        self.assertEqual(question.question_id, 59)
        self.assertEqual(
            {str(option["OptionId"]) for option in question.options},
            {"1"},
        )
        serialized_question = TargetingQuestionSerializer(question).data
        self.assertEqual(
            {str(option["OptionId"]) for option in serialized_question["options"]},
            {"1"},
        )
        quota_details = SurveyQuotaSerializer(self.survey.quotas.get()).data[
            "targeting_details"
        ]
        self.assertEqual(quota_details, [{
            "name": "What is your gender?",
            "question_key": "GENDER",
            "question_id": 59,
            "values": ["Female"],
            "answer_ids": ["2"],
        }])
        self.assertTrue(self.survey.has_quota)
        self.assertIsNotNone(self.survey.detail_synced_at)
        self.assertEqual(self.survey.entry_link, original_link)
        detail_client.get_quota_for_survey.assert_called_once_with(16120319)
        detail_client.get_survey_targeting.assert_called_once_with(16120319)

    @patch("surveys.providers.rmwinsights.resolve_integration_token", return_value="secret")
    def test_disabled_local_prescreener_creates_attempt_and_redirects_directly(self, _token):
        self.integration.local_prescreener_enabled = False
        self.integration.save(update_fields=["local_prescreener_enabled", "updated_at"])
        operator = get_user_model().objects.create_superuser(
            username="rmw-direct-operator",
            email="rmw-direct@example.test",
            password="test-password",
        )

        response = self.client.get(reverse("survey-start"), {
            "surveyId": self.survey.source_key,
            "supplierCode": settings.PUBLIC_SUPPLIER_CODE,
            "userId": str(operator.pk),
            "code": self.survey.local_id,
            "pid": "Px7Qa2B",
        })

        attempt = SurveyAttempt.objects.get(survey=self.survey, platform_user=operator)
        query = parse_qs(urlsplit(response.url).query)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(urlsplit(response.url).hostname, "api.rmwinsights.com")
        self.assertEqual(query["pid"], [attempt.pid])
        self.assertEqual(attempt.pid, "Px7Qa2B")
        self.assertEqual(attempt.status, SurveyAttempt.Status.REDIRECTED)
        self.assertEqual(attempt.answers, {})
        self.assertTrue(
            attempt.upstream_transaction_data["local_prescreener"]["bypassed"]
        )

    def test_quota_answer_ids_remain_scoped_to_their_own_ranges(self):
        TargetingQuestion.objects.create(
            survey=self.survey,
            question_id=1,
            key="AGE",
            text="What is your age?",
            question_type="Numeric",
            options=[{"OptionId": 1, "ageStart": 25, "ageEnd": 34}],
        )
        quota = SurveyQuota.objects.create(
            survey=self.survey,
            source_key="quota-age-18-24",
            quota_id=9002,
            targeting={
                "AGE": [{"OptionId": 1, "ageStart": 18, "ageEnd": 24}],
            },
        )

        detail = SurveyQuotaSerializer(quota).data["targeting_details"][0]

        self.assertEqual(detail["question_id"], 1)
        self.assertEqual(detail["question_key"], "AGE")
        self.assertEqual(detail["values"], ["18\u201324"])
        self.assertEqual(detail["answer_ids"], ["1"])
        self.assertEqual(
            TargetingQuestion.objects.get(survey=self.survey).options,
            [{"OptionId": 1, "ageStart": 25, "ageEnd": 34}],
        )

    @patch("surveys.rmw_callbacks.get_provider")
    def test_unknown_remote_rid_is_attached_to_matching_local_attempt(self, get_provider):
        started = timezone.now() - timedelta(seconds=30)
        attempt = SurveyAttempt.objects.create(
            rid="U9iQZJChXS",
            survey=self.survey,
            client=self.client_record,
            user_id="respondent-1",
            status=SurveyAttempt.Status.REDIRECTED,
            initiation_ip="74.109.113.243",
            initiated_at=started,
        )
        get_provider.return_value.remote_attempt.return_value = {
            "rid": "lGmOI3Sfo3",
            "pid": "ZbOG7dliS",
            "status": "4",
            "survey_source_id": "16120319",
            "entry_ip": "74.109.113.243",
            "initiated_at": (started + timedelta(seconds=19)).isoformat(),
            "callback_at": timezone.now().isoformat(),
            "callback_ip": "52.207.183.194",
            "status_source": "innovatemr_hash_rejected",
            "is_verified": False,
        }

        response = self.client.get(
            reverse("survey-status"),
            {"status": "4", "rid": "lGmOI3Sfo3"},
            REMOTE_ADDR="74.109.113.243",
        )

        attempt.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"status=4&rid={attempt.rid}", response.url)
        self.assertEqual(attempt.status, SurveyAttempt.Status.QUALITY_TERMINATED)
        self.assertEqual(attempt.status_source, "rmwinsights_callback")
        self.assertEqual(attempt.callback_count, 1)
        self.assertEqual(
            attempt.upstream_transaction_data["rmwinsights_callback"]["rid"],
            "lGmOI3Sfo3",
        )

    def test_pid_callback_cleans_to_local_rid_and_renders_both_ids(self):
        attempt = SurveyAttempt.objects.create(
            rid="Local8RidQ",
            pid="Qh7QaI4",
            survey=self.survey,
            client=self.client_record,
            user_id="respondent-direct-pid",
            status=SurveyAttempt.Status.REDIRECTED,
        )

        callback = self.client.get(
            reverse("survey-status"),
            {"status": "4", "rid": attempt.pid},
        )

        attempt.refresh_from_db()
        self.assertEqual(callback.status_code, 302)
        self.assertEqual(
            callback["Location"],
            f"{reverse('survey-status')}?status=4&rid={attempt.rid}",
        )
        self.assertEqual(attempt.status, SurveyAttempt.Status.QUALITY_TERMINATED)
        self.assertEqual(attempt.status_source, "rmwinsights_pid_callback")
        self.assertEqual(attempt.callback_count, 1)

        result = self.client.get(callback["Location"])
        attempt.refresh_from_db()
        self.assertEqual(result.status_code, 200)
        self.assertContains(result, attempt.rid)
        self.assertContains(result, attempt.pid)
        self.assertEqual(attempt.callback_count, 1)

    def test_numeric_rmw_status_is_human_readable_in_term_reports(self):
        attempt = SurveyAttempt.objects.create(
            rid="Local9RidR",
            survey=self.survey,
            client=self.client_record,
            user_id="respondent-numeric-status",
            status=SurveyAttempt.Status.QUALITY_TERMINATED,
            upstream_transaction_data={"browser_return": {"status": "4"}},
        )

        self.assertEqual(provider_outcome(attempt)["status"], "Quality terminated")

    @patch("surveys.rmw_callbacks.get_provider")
    def test_remote_pid_maps_exactly_even_when_respondent_ip_changes(self, get_provider):
        attempt = SurveyAttempt.objects.create(
            rid="Lo9Ca4RidP",
            pid="Px7Qa2B",
            survey=self.survey,
            client=self.client_record,
            user_id="respondent-ip-change",
            status=SurveyAttempt.Status.REDIRECTED,
            initiation_ip="173.34.3.177",
        )
        get_provider.return_value.remote_attempt.return_value = {
            "rid": "Rm8Re3RidX",
            "pid": attempt.pid,
            "status": "4",
            "survey_source_id": "16120319",
            "entry_ip": "24.202.136.229",
            "initiated_at": timezone.now().isoformat(),
            "callback_at": timezone.now().isoformat(),
            "callback_ip": "54.164.191.203",
            "is_verified": False,
        }

        response = self.client.get(
            reverse("survey-status"),
            {"status": "4", "rid": "Rm8Re3RidX"},
            REMOTE_ADDR="24.202.136.229",
        )

        attempt.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(attempt.status, SurveyAttempt.Status.QUALITY_TERMINATED)
        self.assertEqual(attempt.status_source, "rmwinsights_callback")
        self.assertEqual(
            attempt.upstream_transaction_data["rmwinsights_callback"]["pid"],
            "Px7Qa2B",
        )

    @patch("surveys.rmw_callbacks.get_provider")
    def test_reconciliation_recovers_a_missed_terminal_callback(self, get_provider):
        from .rmw_callbacks import reconcile_recent_attempts

        started = timezone.now() - timedelta(minutes=1)
        callback_at = timezone.now()
        attempt = SurveyAttempt.objects.create(
            rid="Local4Rid7",
            survey=self.survey,
            client=self.client_record,
            user_id="respondent-2",
            status=SurveyAttempt.Status.REDIRECTED,
            initiation_ip="74.109.113.243",
            initiated_at=started,
        )
        get_provider.return_value.recent_attempts.return_value = [{
            "rid": "Remote4Rid",
            "status": "4",
            "survey_source_id": "16120319",
            "entry_ip": "74.109.113.243",
            "initiated_at": (started + timedelta(seconds=15)).isoformat(),
            "callback_at": callback_at.isoformat(),
            "callback_ip": "52.207.183.194",
            "is_verified": False,
        }]

        result = reconcile_recent_attempts(self.integration)

        attempt.refresh_from_db()
        self.assertEqual(result, {"reconciled": 1})
        self.assertEqual(attempt.status, SurveyAttempt.Status.QUALITY_TERMINATED)
        self.assertEqual(attempt.status_source, "rmwinsights_api_reconcile")
        self.assertEqual(attempt.callback_ip, "52.207.183.194")
        self.assertEqual(attempt.callback_count, 1)


class InnovateRMWCutoverTests(TestCase):
    def setUp(self):
        self.client_record = Client.objects.create(
            code="innovate-cutover", name="InnovateMR", provider_code="innovatemr"
        )
        self.legacy = ClientIntegration.objects.create(
            client=self.client_record,
            name="Enligne legacy",
            provider_code="enligne",
            base_url="https://enlignesurvey.com/get/api_feed/legacy-feed",
            is_active=True,
            scheduled_sync_enabled=True,
        )
        self.legacy_live = Survey.objects.create(
            client=self.client_record,
            integration=self.legacy,
            source_key="16100001",
            source_id=16100001,
            name="Legacy live",
            status=Survey.Status.LIVE,
        )
        self.legacy_closed = Survey.objects.create(
            client=self.client_record,
            integration=self.legacy,
            source_key="16100002",
            source_id=16100002,
            name="Legacy closed",
            status=Survey.Status.CLOSED,
        )
        self.attempt = SurveyAttempt.objects.create(
            rid="OldRev1234",
            survey=self.legacy_closed,
            client=self.client_record,
            user_id="historical-user",
            status=SurveyAttempt.Status.COMPLETED,
            payable_cpi_snapshot="2.50",
        )

    @patch.dict("os.environ", {"RMW_CUTOVER_API_KEY": "new-secret"})
    @patch("surveys.management.commands.cutover_innovate_rmw.sync_client_integration")
    @patch("surveys.management.commands.cutover_innovate_rmw.get_provider")
    def test_cutover_closes_legacy_without_deleting_history(self, get_provider, sync_inventory):
        get_provider.return_value.test_connection.return_value = {"available_live_surveys": 2475}
        sync_inventory.return_value = SimpleNamespace(
            status="success", fetched_full=2475, created=2475, updated=0
        )

        call_command("cutover_innovate_rmw", client=self.client_record.code, confirm=True)

        self.legacy.refresh_from_db()
        self.legacy_live.refresh_from_db()
        self.assertFalse(self.legacy.is_active)
        self.assertFalse(self.legacy.scheduled_sync_enabled)
        self.assertEqual(self.legacy_live.status, Survey.Status.CLOSED)
        self.assertTrue(Survey.objects.filter(pk=self.legacy_closed.pk).exists())
        self.assertTrue(SurveyAttempt.objects.filter(pk=self.attempt.pk).exists())
        replacement = ClientIntegration.objects.get(
            client=self.client_record, provider_code="rmwinsights"
        )
        self.assertTrue(replacement.is_active)
        self.assertTrue(replacement.scheduled_sync_enabled)
