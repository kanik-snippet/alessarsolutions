"""Permission-aware CPI and supplier labels for Traffic Reports.

The project inventory and respondent reports must show the same commercial
price to a scoped user.  Source/client CPI is reserved for Super Admin;
other viewers see only the price after their supplier allocation and/or role
visibility percentage has been applied.
"""

from decimal import Decimal, ROUND_HALF_UP

from django.db.models import DecimalField, ExpressionWrapper, Sum, Value
from django.db.models.functions import Coalesce, Least, Round

from accounts.models import EmployeeProfile
from vendors.access import is_external_vendor_scope


MONEY_QUANTUM = Decimal("0.01")
MANAGER_CPI_CAP = Decimal("5.00")
ADMIN_ROLE_SLUGS = {"admin", "super-admin"}


def _money(value):
    """Normalize a nullable CPI value without introducing float rounding."""

    if value is None:
        return None
    return Decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _percentage(value):
    """Clamp a configured visibility percentage to the supported 0-100 range."""

    return min(Decimal("100.00"), max(Decimal("0.00"), Decimal(value)))


def apply_percentage(value, percent):
    """Apply a CPI visibility percentage and return a currency-safe value."""

    value = _money(value)
    if value is None:
        return None
    return (value * _percentage(percent) / Decimal("100.00")).quantize(
        MONEY_QUANTUM,
        rounding=ROUND_HALF_UP,
    )


def role_visibility_percent(user):
    """Return the role percentage that applies to an employee viewer or actor."""

    if getattr(user, "is_superuser", False):
        return Decimal("100.00")
    profile = getattr(user, "employee_profile", None) if user else None
    role = getattr(profile, "role", None) if profile else None
    if role and role.slug in {"super-admin", "superadmin"}:
        return Decimal("100.00")
    if profile and profile.account_type == EmployeeProfile.AccountType.EMPLOYEE and role:
        return _percentage(role.cpi_visibility_percent)
    return Decimal("100.00")


def cap_manager_cpi(user, value):
    """Keep Alessar's Manager CPI cap after all percentage cuts are applied."""

    value = _money(value)
    profile = getattr(user, "employee_profile", None) if user else None
    role = getattr(profile, "role", None) if profile else None
    if (
        value is not None
        and not getattr(user, "is_superuser", False)
        and profile
        and profile.account_type == EmployeeProfile.AccountType.EMPLOYEE
        and role
        and role.slug == "manager"
    ):
        return min(value, MANAGER_CPI_CAP)
    return value


def _manager_cap_applies(user):
    profile = getattr(user, "employee_profile", None) if user else None
    role = getattr(profile, "role", None) if profile else None
    return bool(
        not getattr(user, "is_superuser", False)
        and profile
        and profile.account_type == EmployeeProfile.AccountType.EMPLOYEE
        and role
        and role.slug == "manager"
    )


def can_view_report_commercials(user):
    """Allow source/supplier CPI columns only to platform admin scopes.

    An external supplier must never gain source CPI merely because an old or
    custom role happens to use the ``admin`` slug.
    """

    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    if is_external_vendor_scope(user):
        return False
    profile = getattr(user, "employee_profile", None)
    role = getattr(profile, "role", None) if profile else None
    return bool(role and role.slug in ADMIN_ROLE_SLUGS)


def can_view_actual_cpi(user):
    """Only Super Admin scope bypasses the configured role CPI cut."""

    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    profile = getattr(user, "employee_profile", None)
    role = getattr(profile, "role", None) if profile else None
    return bool(
        profile
        and profile.account_type == EmployeeProfile.AccountType.EMPLOYEE
        and role
        and role.slug in {"super-admin", "superadmin"}
    )


def viewer_attempt_cpi(attempt, viewer, *, current=False):
    """Return the only CPI a viewer may see for one attempt.

    External supplier scopes start from the immutable supplier-payable snapshot
    (or apply its snapshotted cut to current CPI). Internal employee scopes
    start from client CPI. The viewer's role percentage is applied last so the
    result matches the Projects page.
    """

    source = attempt.survey.cpi if current else attempt.source_cpi_snapshot
    if can_view_actual_cpi(viewer):
        return _money(source)

    base = source
    if is_external_vendor_scope(viewer):
        if current:
            cut = Decimal(attempt.cpi_cut_percent_snapshot or 0)
            base = apply_percentage(source, Decimal("100.00") - cut)
        else:
            base = attempt.payable_cpi_snapshot
            if base is None:
                base = source
    return cap_manager_cpi(
        viewer,
        apply_percentage(base, role_visibility_percent(viewer)),
    )


def annotate_viewer_revenue(queryset, viewer, *, alias="viewer_revenue"):
    """Annotate row-level revenue after the viewer's cut and Manager cap."""

    money_field = DecimalField(max_digits=18, decimal_places=2)
    calculation_field = DecimalField(max_digits=30, decimal_places=10)
    zero = Value(Decimal("0.00"), output_field=money_field)
    source = Coalesce("source_cpi_snapshot", zero, output_field=money_field)
    if can_view_actual_cpi(viewer):
        base = source
        percent = Decimal("100.00")
    else:
        base = (
            Coalesce(
                "payable_cpi_snapshot",
                "source_cpi_snapshot",
                zero,
                output_field=money_field,
            )
            if is_external_vendor_scope(viewer)
            else source
        )
        percent = role_visibility_percent(viewer)
    visible = Round(
        ExpressionWrapper(
            base
            * Value(
                percent / Decimal("100.00"),
                output_field=calculation_field,
            ),
            output_field=calculation_field,
        ),
        precision=2,
        output_field=money_field,
    )
    if _manager_cap_applies(viewer):
        visible = Least(
            visible,
            Value(MANAGER_CPI_CAP, output_field=money_field),
            output_field=money_field,
        )
    return queryset.annotate(**{alias: visible})


def viewer_revenue_total(queryset, viewer) -> Decimal:
    """Sum revenue after applying the exact displayed CPI rule to every row."""

    total = annotate_viewer_revenue(queryset, viewer).aggregate(
        total=Sum("viewer_revenue", default=Decimal("0.00"))
    )["total"] or Decimal("0.00")
    return _money(total) or Decimal("0.00")


def supplier_cpi_for_admin(attempt):
    """Return the supplier/organization payout CPI visible in an admin export.

    The supplier-allocation snapshot is applied first. For an internal
    organization employee, the employee's assigned role percentage is then
    applied so a TL configured at 70% exports at 70%, while client CPI remains
    untouched in the adjacent admin-only columns.
    """

    base = attempt.payable_cpi_snapshot
    if base is None:
        base = attempt.source_cpi_snapshot
    return cap_manager_cpi(
        attempt.platform_user,
        apply_percentage(base, role_visibility_percent(attempt.platform_user)),
    )


def supplier_label_for_admin(attempt):
    """Resolve external supplier name or an organization member's Sub-branch."""

    supplier = attempt.vendor
    supplier_profile = getattr(supplier, "employee_profile", None) if supplier else None
    if supplier_profile and supplier_profile.account_type == EmployeeProfile.AccountType.EXTERNAL_VENDOR:
        return supplier.get_full_name() or supplier.username

    actor = attempt.platform_user
    actor_profile = getattr(actor, "employee_profile", None) if actor else None
    if actor_profile and actor_profile.account_type == EmployeeProfile.AccountType.EXTERNAL_VENDOR:
        return actor.get_full_name() or actor.username

    unit = getattr(actor_profile, "organization_unit", None) if actor_profile else None
    visited = set()
    while unit and unit.pk not in visited:
        visited.add(unit.pk)
        if unit.unit_type == "sub_branch":
            return unit.name
        unit = unit.parent

    if supplier:
        return supplier.get_full_name() or supplier.username
    return ""
