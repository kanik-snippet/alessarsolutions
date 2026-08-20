"""Set, inspect or clear one user's exact legacy-tool revenue balance."""

from datetime import datetime, time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from surveys.models import HistoricalRevenueBalance


class Command(BaseCommand):
    help = "Set an idempotent per-user historical revenue opening balance without creating fake hits."

    def add_arguments(self, parser):
        parser.add_argument("--user", required=True, help="Exact username, email or numeric user ID.")
        parser.add_argument("--amount", help="Exact final legacy revenue amount, for example 1250.75.")
        parser.add_argument("--currency", default="USD", help="Currency code; currently USD only.")
        parser.add_argument("--as-of", dest="as_of", help="ISO date/time or YYYY-MM-DD effective date.")
        parser.add_argument("--note", default="", help="Optional audit note (maximum 240 characters).")
        parser.add_argument("--show", action="store_true", help="Show the current balance without changing it.")
        parser.add_argument("--clear", action="store_true", help="Delete the current historical balance.")
        parser.add_argument("--dry-run", action="store_true", help="Validate and preview without writing.")

    @staticmethod
    def _user(identifier):
        User = get_user_model()
        user = User.objects.filter(username__iexact=identifier).first()
        if user is None and identifier.isdigit():
            user = User.objects.filter(pk=int(identifier)).first()
        if user is None:
            matches = list(User.objects.filter(email__iexact=identifier)[:2])
            if len(matches) > 1:
                raise CommandError("More than one account uses that email; use username or user ID.")
            user = matches[0] if matches else None
        if user is None:
            raise CommandError(f"User not found: {identifier}")
        return user

    @staticmethod
    def _effective_at(value):
        if not value:
            return timezone.now()
        parsed = parse_datetime(value)
        if parsed is None:
            parsed_date = parse_date(value)
            if parsed_date:
                parsed = datetime.combine(parsed_date, time.min)
        if parsed is None:
            raise CommandError("--as-of must be an ISO date/time or YYYY-MM-DD.")
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed

    def handle(self, *args, **options):
        if options["show"] and options["clear"]:
            raise CommandError("Use only one of --show or --clear.")
        if (options["show"] or options["clear"]) and options.get("amount") is not None:
            raise CommandError("--amount cannot be combined with --show or --clear.")
        user = self._user(str(options["user"]).strip())
        current = HistoricalRevenueBalance.objects.filter(user=user).first()

        if options["show"]:
            if current is None:
                self.stdout.write(f"user={user.username} historical_revenue=not-set")
            else:
                self.stdout.write(
                    f"user={user.username} amount={current.amount:.2f} "
                    f"currency={current.currency} effective_at={current.effective_at.isoformat()} "
                    f"note={current.note or '-'}"
                )
            return

        if options["clear"]:
            if options["dry_run"]:
                self.stdout.write(f"DRY RUN: would clear user={user.username}")
                return
            deleted, _ = HistoricalRevenueBalance.objects.filter(user=user).delete()
            self.stdout.write(self.style.SUCCESS(
                f"Historical revenue {'cleared' if deleted else 'was already unset'} for user={user.username}."
            ))
            return

        if options.get("amount") is None:
            raise CommandError("Provide --amount, --show or --clear.")
        try:
            amount = Decimal(str(options["amount"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise CommandError("--amount must be a valid decimal value.") from exc
        if amount < 0:
            raise CommandError("--amount cannot be negative.")
        currency = str(options["currency"] or "").strip().upper()
        if currency != "USD":
            raise CommandError("Only USD historical revenue is supported by the current reports.")
        note = str(options["note"] or "").strip()
        if len(note) > 240:
            raise CommandError("--note cannot exceed 240 characters.")
        effective_at = self._effective_at(options.get("as_of"))
        preview = (
            f"user={user.username} previous={current.amount if current else 'not-set'} "
            f"new={amount:.2f} currency={currency} effective_at={effective_at.isoformat()}"
        )
        if options["dry_run"]:
            self.stdout.write(f"DRY RUN: {preview}")
            return

        try:
            with transaction.atomic():
                balance = HistoricalRevenueBalance.objects.select_for_update().filter(user=user).first()
                created = balance is None
                if balance is None:
                    balance = HistoricalRevenueBalance(user=user)
                balance.amount = amount
                balance.currency = currency
                balance.effective_at = effective_at
                balance.note = note
                balance.full_clean()
                balance.save()
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc
        action = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Historical revenue {action}: {preview}"))
