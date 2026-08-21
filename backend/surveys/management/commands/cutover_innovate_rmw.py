"""Non-destructively replace legacy Innovate inventory with RMW Insights."""

import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from surveys.models import Survey, SurveyAttempt
from surveys.provider_services import sync_client_integration
from surveys.providers import get_provider
from vendors.credentials import set_integration_token
from vendors.models import Client, ClientIntegration


class Command(BaseCommand):
    help = (
        "Sync RMW live inventory first, then close legacy Innovate/Enligne live rows "
        "and deactivate their integrations without deleting history."
    )

    def add_arguments(self, parser):
        parser.add_argument("--client", required=True, help="Client code, numeric ID or exact name.")
        parser.add_argument("--token-env", default="RMW_CUTOVER_API_KEY")
        parser.add_argument("--integration-name", default="Innovate RMW Live")
        parser.add_argument(
            "--base-url",
            default="https://api.rmwinsights.com/api/v1/surveys/",
        )
        parser.add_argument("--confirm", action="store_true")

    @staticmethod
    def _client(identifier):
        query = Client.objects.filter(code__iexact=identifier)
        if identifier.isdigit():
            query = Client.objects.filter(pk=int(identifier)) | query
        client = query.order_by("pk").first()
        if client is None:
            matches = list(Client.objects.filter(name__iexact=identifier)[:2])
            if len(matches) > 1:
                raise CommandError("More than one client has that name; use its code or ID.")
            client = matches[0] if matches else None
        if client is None:
            raise CommandError(f"Client not found: {identifier}")
        return client

    def handle(self, *args, **options):
        if not options["confirm"]:
            raise CommandError("Add --confirm to perform the non-destructive cutover.")
        token = os.getenv(str(options["token_env"] or "").strip(), "").strip()
        if not token:
            raise CommandError("The cutover token environment variable is not configured.")
        client = self._client(str(options["client"]).strip())
        name = str(options["integration_name"]).strip()
        integration, _ = ClientIntegration.objects.get_or_create(
            client=client,
            name=name,
            defaults={
                "provider_code": "rmwinsights",
                "base_url": options["base_url"],
                "is_active": True,
                "scheduled_sync_enabled": False,
                "sync_interval_seconds": 60,
                "detail_refresh_batch": 20,
                "config": {"page_size": 100, "max_pages": 100, "detail_refresh_batch": 20},
            },
        )
        integration.provider_code = "rmwinsights"
        integration.base_url = options["base_url"]
        integration.is_active = True
        integration.scheduled_sync_enabled = False
        integration.sync_interval_seconds = 60
        integration.detail_refresh_batch = 20
        integration.config = {
            **(integration.config or {}),
            "page_size": 100,
            "max_pages": 100,
            "detail_refresh_batch": 20,
        }
        integration.save()
        set_integration_token(integration, token)

        # Authenticate before changing legacy state, but do not call the UI
        # connection-test service here: that service intentionally enables the
        # scheduler and could race this one-time full cutover sync.
        test_result = get_provider(integration).test_connection()
        run = sync_client_integration(integration, refresh_details=False)
        if run.status == "failed":
            raise CommandError("RMW inventory sync failed; legacy integrations were not changed.")

        legacy = ClientIntegration.objects.filter(
            client=client,
            provider_code__in=("innovatemr", "enligne"),
        ).exclude(pk=integration.pk)
        legacy_ids = list(legacy.values_list("pk", flat=True))
        attempts_before = SurveyAttempt.objects.filter(survey__integration_id__in=legacy_ids).count()
        now = timezone.now()
        with transaction.atomic():
            archived = Survey.objects.filter(
                integration_id__in=legacy_ids,
                status=Survey.Status.LIVE,
            ).update(status=Survey.Status.CLOSED, updated_at=now)
            deactivated = legacy.update(
                is_active=False,
                scheduled_sync_enabled=False,
                updated_at=now,
            )
            ClientIntegration.objects.filter(pk=integration.pk).update(
                is_active=True,
                scheduled_sync_enabled=True,
                last_test_status="success",
                last_tested_at=now,
                last_test_error="",
                updated_at=now,
            )
        attempts_after = SurveyAttempt.objects.filter(survey__integration_id__in=legacy_ids).count()
        if attempts_before != attempts_after:
            raise CommandError("Historical attempt count changed unexpectedly during cutover.")
        self.stdout.write(self.style.SUCCESS(
            "RMW cutover complete: "
            f"remote_available={test_result['available_live_surveys']} fetched={run.fetched_full} "
            f"created={run.created} updated={run.updated} archived_legacy_live={archived} "
            f"deactivated_integrations={deactivated} preserved_attempts={attempts_after}."
        ))
