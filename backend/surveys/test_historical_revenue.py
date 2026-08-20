from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from vendors.models import Client

from .models import HistoricalRevenueBalance, Survey, SurveyAttempt


class HistoricalRevenueTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_superuser(
            username="historical-owner",
            email="historical-owner@example.test",
            password="test-password",
        )
        self.user = get_user_model().objects.create_user(
            username="legacy-user",
            email="legacy-user@example.test",
        )
        self.empty_user = get_user_model().objects.create_user(username="legacy-empty-user")
        self.survey = Survey.objects.create(
            client=Client.objects.create(code="historical-client", name="Historical Client"),
            source_id=98765001,
            name="Historical revenue test",
            company_name="InnovateMR",
            country="United States",
            country_code="US",
            cpi="2.50",
        )
        SurveyAttempt.objects.create(
            rid="Hr1Aa2Bb3C",
            survey=self.survey,
            platform_user=self.user,
            user_id=str(self.user.pk),
            status=SurveyAttempt.Status.COMPLETED,
            source_cpi_snapshot="2.50",
            payable_cpi_snapshot="2.50",
            cpi_currency_snapshot="USD",
        )
        self.api = APIClient()
        self.api.force_authenticate(self.owner)

    def test_command_sets_updates_shows_and_clears_one_balance(self):
        output = StringIO()
        call_command(
            "set_user_historical_revenue",
            user=self.user.username,
            amount="100.125",
            as_of="2026-08-01",
            note="Old tool closing total",
            stdout=output,
        )
        balance = HistoricalRevenueBalance.objects.get(user=self.user)
        self.assertEqual(balance.amount, Decimal("100.13"))
        self.assertEqual(balance.note, "Old tool closing total")

        call_command(
            "set_user_historical_revenue",
            user=str(self.user.pk),
            amount="125.50",
            stdout=StringIO(),
        )
        self.assertEqual(HistoricalRevenueBalance.objects.filter(user=self.user).count(), 1)
        balance.refresh_from_db()
        self.assertEqual(balance.amount, Decimal("125.50"))

        shown = StringIO()
        call_command(
            "set_user_historical_revenue",
            user=self.user.email,
            show=True,
            stdout=shown,
        )
        self.assertIn("amount=125.50", shown.getvalue())

        call_command(
            "set_user_historical_revenue",
            user=self.user.username,
            clear=True,
            stdout=StringIO(),
        )
        self.assertFalse(HistoricalRevenueBalance.objects.filter(user=self.user).exists())

    def test_report_adds_exact_balance_without_fake_hits(self):
        call_command(
            "set_user_historical_revenue",
            user=self.user.username,
            amount="100.00",
            as_of="2026-08-01",
            stdout=StringIO(),
        )
        response = self.api.get(reverse("survey-attempt-list"), {"user": self.user.pk})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"]["total"], 1)
        self.assertEqual(response.data["summary"]["completed"], 1)
        self.assertEqual(
            Decimal(str(response.data["summary"]["total_revenue"])),
            Decimal("102.50"),
        )

        project_filtered = self.api.get(
            reverse("survey-attempt-list"),
            {"user": self.user.pk, "internal_id": self.survey.local_id},
        )
        self.assertEqual(
            Decimal(str(project_filtered.data["summary"]["total_revenue"])),
            Decimal("2.50"),
        )
        terminated_only = self.api.get(
            reverse("survey-attempt-list"),
            {"user": self.user.pk, "status": SurveyAttempt.Status.TERMINATED},
        )
        self.assertEqual(
            Decimal(str(terminated_only.data["summary"]["total_revenue"])),
            Decimal("0.00"),
        )

    def test_balance_only_user_can_be_selected_without_creating_attempts(self):
        call_command(
            "set_user_historical_revenue",
            user=self.empty_user.username,
            amount="75.25",
            stdout=StringIO(),
        )
        response = self.api.get(reverse("survey-attempt-list"), {"user": self.empty_user.pk})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["summary"]["total"], 0)
        self.assertEqual(
            Decimal(str(response.data["summary"]["total_revenue"])),
            Decimal("75.25"),
        )

    def test_superuser_can_assign_revenue_from_simple_admin_form(self):
        self.client.force_login(self.owner)
        add_url = reverse("admin:surveys_historicalrevenuebalance_add")

        form_response = self.client.get(add_url)
        self.assertEqual(form_response.status_code, 200)
        self.assertContains(form_response, 'name="user"')
        self.assertContains(form_response, 'name="amount"')
        self.assertNotContains(form_response, 'name="currency"')
        self.assertNotContains(form_response, 'name="effective_at"')

        save_response = self.client.post(
            add_url,
            {"user": self.empty_user.pk, "amount": "450.75", "_save": "Save"},
        )
        self.assertEqual(save_response.status_code, 302)
        balance = HistoricalRevenueBalance.objects.get(user=self.empty_user)
        self.assertEqual(balance.amount, Decimal("450.75"))
        self.assertEqual(balance.currency, "USD")
