from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from vendors.models import Client, ClientIntegration

from .models import Survey, SurveyAttempt
from .providers.rmwinsights import RMWInsightsProvider


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
            SimpleNamespace(rid="Ab3De6Gh9J"),
            {"ignored": "answer"},
        )
        query = parse_qs(urlsplit(outbound).query)

        self.assertEqual(query["pid"], ["Ab3De6Gh9J"])
        self.assertEqual(query["key"], ["key-id"])
        self.assertEqual(query["token"], ["signed-token"])
        self.assertEqual(query["survey"], ["20260800002961"])


class RMWInsightsDetailsTests(TestCase):
    def setUp(self):
        self.client_record = Client.objects.create(
            code="rmw-details", name="InnovateMR", provider_code="innovatemr"
        )
        self.integration = ClientIntegration.objects.create(
            client=self.client_record,
            name="RMW live",
            provider_code="rmwinsights",
            base_url="https://api.rmwinsights.com/api/v1/surveys/",
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
    def test_refresh_details_replaces_quota_and_targeting(self, _token):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            **remote_row(),
            "quotas": [{
                "id": 44, "quota_id": 9001, "name": "Total", "sample_size": 175,
                "remaining": 170, "completes": 5, "clicks": 12, "status": "Open",
                "targeting": {"questions": []},
            }],
            "targeting_questions": [{
                "id": 8, "question_id": 59, "key": "GENDER",
                "text": "What is your gender?", "question_type": "single",
                "category": "Profile", "options": [
                    {"OptionId": "1", "OptionText": "Male"},
                ],
            }],
        }
        session = Mock()
        session.get.return_value = response

        RMWInsightsProvider(self.integration, session=session).refresh_details(self.survey)

        self.survey.refresh_from_db()
        self.assertEqual(self.survey.quotas.count(), 1)
        self.assertEqual(self.survey.targeting_questions.count(), 1)
        self.assertEqual(self.survey.targeting_questions.get().question_id, 59)
        self.assertTrue(self.survey.has_quota)
        self.assertIsNotNone(self.survey.detail_synced_at)
        self.assertTrue(session.get.call_args.args[0].endswith("/20260800002961/"))


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
