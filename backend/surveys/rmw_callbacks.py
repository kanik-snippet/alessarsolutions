"""Resolve and reconcile RMW's internal RID with an Alessar attempt."""

from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from vendors.models import ClientIntegration

from .models import SurveyAttempt
from .providers import ProviderError, get_provider


TERMINAL_STATUSES = {
    SurveyAttempt.Status.COMPLETED,
    SurveyAttempt.Status.TERMINATED,
    SurveyAttempt.Status.OVER_QUOTA,
    SurveyAttempt.Status.QUALITY_TERMINATED,
}


def safe_remote_attempt(payload):
    """Keep only callback identity/audit fields; never persist remote URLs or PII."""

    return {
        key: payload.get(key)
        for key in (
            "rid", "pid", "status", "status_label", "survey_source_id",
            "entry_ip", "initiation_ip", "callback_ip", "initiated_at",
            "callback_at", "status_source", "is_verified",
        )
        if payload.get(key) not in (None, "")
    }


def matching_local_attempt(integration, payload, *, request_ip=""):
    """Match an authenticated remote attempt by exact PID, then legacy audit signals."""

    remote_rid = str(payload.get("rid") or "").strip()
    stored = SurveyAttempt.objects.filter(
        survey__integration=integration,
        upstream_transaction_data__rmwinsights_callback__rid=remote_rid,
    ).first()
    if stored is not None:
        return stored

    survey_id = str(payload.get("survey_source_id") or "").strip()
    if not remote_rid or not survey_id:
        return None
    survey_identity = Q(survey__source_key=survey_id)
    if survey_id.isdigit():
        survey_identity |= Q(survey__source_id=int(survey_id))

    # New RMW journeys receive our 6-9 character platform PID. This lookup is
    # globally unique locally and remains safe even when a respondent's IP
    # changes between the two pre-screeners or during the provider survey.
    remote_pid = str(payload.get("pid") or "").strip()
    if remote_pid.isalnum() and 6 <= len(remote_pid) <= 9:
        exact = SurveyAttempt.objects.filter(
            survey__integration=integration,
            pid=remote_pid,
        ).filter(survey_identity).first()
        if exact is not None:
            return exact

    # Historical RMW attempts were sent our 10-character RID in a field RMW
    # did not retain. Keep the previous bounded heuristic only for those rows.
    entry_ip = str(payload.get("entry_ip") or payload.get("initiation_ip") or "").strip()
    remote_started = parse_datetime(str(payload.get("initiated_at") or ""))
    if not entry_ip or remote_started is None:
        return None
    if timezone.is_naive(remote_started):
        remote_started = timezone.make_aware(remote_started, timezone.get_current_timezone())
    if request_ip and request_ip != entry_ip:
        return None
    candidates = list(
        SurveyAttempt.objects.filter(
            survey__integration=integration,
            initiation_ip=entry_ip,
            status__in=[SurveyAttempt.Status.INITIATED, SurveyAttempt.Status.REDIRECTED],
            initiated_at__gte=remote_started - timedelta(minutes=5),
            initiated_at__lte=remote_started + timedelta(minutes=5),
        ).filter(survey_identity).order_by("initiated_at")[:10]
    )
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda attempt: abs((attempt.initiated_at - remote_started).total_seconds()),
    )


def resolve_remote_callback(remote_rid, status_code, *, request_ip=""):
    """Authenticate an unknown RMW RID and resolve its originating local attempt."""

    for integration in ClientIntegration.objects.filter(
        provider_code="rmwinsights",
        is_active=True,
    ).select_related("client"):
        try:
            payload = get_provider(integration).remote_attempt(remote_rid)
        except ProviderError:
            continue
        if str(payload.get("status") or "") != str(status_code):
            return None, {}
        attempt = matching_local_attempt(integration, payload, request_ip=request_ip)
        if attempt is not None:
            return attempt, safe_remote_attempt(payload)
    return None, {}


def reconcile_recent_attempts(integration, *, limit=100):
    """Recover terminal results even when RMW's browser redirect was missed."""

    provider = get_provider(integration)
    reconciled = 0
    for payload in provider.recent_attempts(limit=limit):
        status_code = str(payload.get("status") or "")
        if status_code not in TERMINAL_STATUSES:
            continue
        attempt = matching_local_attempt(integration, payload)
        if attempt is None:
            continue
        with transaction.atomic():
            locked = SurveyAttempt.objects.select_for_update().get(pk=attempt.pk)
            audit = dict(locked.upstream_transaction_data or {})
            audit["rmwinsights_callback"] = safe_remote_attempt(payload)
            locked.upstream_transaction_data = audit
            if locked.callback_at is None and locked.status in {
                SurveyAttempt.Status.INITIATED,
                SurveyAttempt.Status.REDIRECTED,
            }:
                remote_callback_at = parse_datetime(str(payload.get("callback_at") or ""))
                if remote_callback_at is None:
                    remote_callback_at = timezone.now()
                elif timezone.is_naive(remote_callback_at):
                    remote_callback_at = timezone.make_aware(
                        remote_callback_at, timezone.get_current_timezone()
                    )
                locked.status = status_code
                locked.callback_at = remote_callback_at
                locked.last_callback_at = remote_callback_at
                locked.callback_ip = str(payload.get("callback_ip") or "") or None
                locked.callback_count += 1
                locked.status_source = "rmwinsights_api_reconcile"
                locked.is_verified = bool(payload.get("is_verified"))
                locked.loi_seconds = locked.calculate_loi_seconds(remote_callback_at)
                locked.save(update_fields=[
                    "status", "callback_at", "last_callback_at", "callback_ip",
                    "callback_count", "status_source", "is_verified", "loi_seconds",
                    "upstream_transaction_data", "updated_at",
                ])
                from vendors.services import finalize_attempt_capacity

                finalize_attempt_capacity(locked)
                reconciled += 1
            else:
                locked.save(update_fields=["upstream_transaction_data", "updated_at"])
    return {"reconciled": reconciled}
