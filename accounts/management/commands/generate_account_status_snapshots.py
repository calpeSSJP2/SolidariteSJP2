from django.core.management.base import BaseCommand
from django.utils import timezone
from calendar import monthrange
from datetime import date
from decimal import Decimal

from accounts.models import ( AccountStatusHistory, AccountStatusSnapshot)

class Command(BaseCommand):
    help = "Generate monthly account status snapshots"

    def add_arguments(self, parser):
        parser.add_argument(  "--year",
            type=int,
            help="Year to generate snapshots for (default: current year)" )
        parser.add_argument( "--month", type=int,
            help="Month to generate snapshots for (default: current month)" )

    def handle(self, *args, **options):
        today = timezone.now().date()

        year = options["year"] or today.year
        month = options["month"] or today.month

        self.stdout.write(
            self.style.NOTICE(
                f"Generating account status snapshots for {year}-{month:02d}"))

        self.generate_snapshots(year, month)

        self.stdout.write(
            self.style.SUCCESS("Account status snapshots generated successfully.") )

    # --------------------------------------------------
    # CORE SNAPSHOT LOGIC
    # --------------------------------------------------
    def generate_snapshots(self, year, month):
        month_start = date(year, month, 1)
        month_end = date(year, month, monthrange(year, month)[1])
        days_in_month = monthrange(year, month)[1]
        histories = AccountStatusHistory.objects.select_related("account")

        for history in histories:
            start = history.started_on.date()
            end = history.ended_on.date() if history.ended_on else timezone.now().date()

            # Calculate overlap
            actual_start = max(start, month_start)
            actual_end = min(end, month_end)

            if actual_start > actual_end:
                continue

            days_in_status = (actual_end - actual_start).days + 1
            months_fraction = Decimal(days_in_status) / Decimal(days_in_month)

            AccountStatusSnapshot.objects.update_or_create(
                account=history.account,
                year=year,
                month=month,
                status_type=history.status_type,
                defaults={
                    "days_in_status": days_in_status,
                    "months_fraction": months_fraction.quantize(Decimal("0.01"))
                })
