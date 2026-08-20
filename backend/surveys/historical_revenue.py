"""Safe aggregation of exact legacy-tool opening revenue balances."""

from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accounts.access import activity_visible_user_ids

from .models import HistoricalRevenueBalance, SurveyAttempt


ZERO = Decimal("0.00")
UNATTRIBUTED_FILTERS = {
    "country", "company", "client", "buyer_id", "survey_id", "internal_id",
    "entry_ip", "exit_ip", "callback_from", "callback_to",
}


def _csv_values(value):
    return {part.strip() for part in str(value or "").split(",") if part.strip()}


def _hierarchy_q(level, value):
    values = _csv_values(value)
    ids = {int(item) for item in values if item.isdigit()}
    labels = {item for item in values if not item.isdigit()}
    unit = "user__employee_profile__organization_unit"
    query = Q()
    has_query = False
    if level == "branch":
        if ids:
            query |= (
                Q(**{f"{unit}_id__in": ids, f"{unit}__unit_type": "branch"})
                | Q(**{f"{unit}__parent_id__in": ids, f"{unit}__parent__unit_type": "branch"})
                | Q(**{f"{unit}__parent__parent_id__in": ids, f"{unit}__parent__parent__unit_type": "branch"})
            )
            has_query = True
        if labels:
            query |= (
                Q(**{f"{unit}__name__in": labels, f"{unit}__unit_type": "branch"})
                | Q(**{f"{unit}__parent__name__in": labels, f"{unit}__parent__unit_type": "branch"})
                | Q(**{f"{unit}__parent__parent__name__in": labels, f"{unit}__parent__parent__unit_type": "branch"})
                | Q(user__employee_profile__company_name__in=labels)
            )
            has_query = True
    elif level == "sub_branch":
        if ids:
            query |= (
                Q(**{f"{unit}_id__in": ids, f"{unit}__unit_type": "sub_branch"})
                | Q(**{f"{unit}__parent_id__in": ids, f"{unit}__parent__unit_type": "sub_branch"})
            )
            has_query = True
        if labels:
            query |= (
                Q(**{f"{unit}__name__in": labels, f"{unit}__unit_type": "sub_branch"})
                | Q(**{f"{unit}__parent__name__in": labels, f"{unit}__parent__unit_type": "sub_branch"})
                | Q(user__employee_profile__department__in=labels)
            )
            has_query = True
    elif level == "shift":
        if ids:
            query |= Q(**{f"{unit}_id__in": ids, f"{unit}__unit_type": "shift"})
            has_query = True
        if labels:
            query |= Q(**{f"{unit}__name__in": labels, f"{unit}__unit_type": "shift"})
            has_query = True
    return query if has_query else None


def _aware_datetime(value):
    parsed = parse_datetime(str(value or ""))
    if parsed and timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def historical_revenue_total(viewer, params) -> Decimal:
    """Return exact legacy revenue compatible with the active Traffic filters.

    The balance is already a final historical amount, so role CPI percentages
    and per-project caps are intentionally not applied again. Filters that need
    a project/client/country attribution exclude it because an opening balance
    has no honest value for those dimensions.
    """

    if any(str(params.get(key) or "").strip() for key in UNATTRIBUTED_FILTERS):
        return ZERO
    statuses = _csv_values(params.get("status"))
    if statuses and SurveyAttempt.Status.COMPLETED not in statuses:
        return ZERO

    queryset = HistoricalRevenueBalance.objects.filter(
        user_id__in=activity_visible_user_ids(viewer),
        currency="USD",
    )
    selected_users = _csv_values(params.get("user"))
    if selected_users:
        if any(not value.isdigit() for value in selected_users):
            return ZERO
        queryset = queryset.filter(user_id__in={int(value) for value in selected_users})

    for level in ("branch", "sub_branch", "shift"):
        hierarchy_query = _hierarchy_q(level, params.get(level))
        if hierarchy_query is not None:
            queryset = queryset.filter(hierarchy_query)

    search = str(params.get("search") or "").strip()
    if search:
        queryset = queryset.filter(
            Q(user__username__icontains=search)
            | Q(user__email__icontains=search)
            | Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
        )
    initiated_from = _aware_datetime(params.get("initiated_from"))
    initiated_to = _aware_datetime(params.get("initiated_to"))
    if initiated_from:
        queryset = queryset.filter(effective_at__gte=initiated_from)
    if initiated_to:
        queryset = queryset.filter(effective_at__lte=initiated_to)
    return queryset.aggregate(total=Sum("amount", default=ZERO))["total"] or ZERO
