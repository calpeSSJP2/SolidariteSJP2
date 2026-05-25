from decimal import Decimal, ROUND_DOWN
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from transact1_regular_deposit.models import SJP2Transaction
from accounts.models import MemberAccount, SJP2_Account
from .models import YearlyInterestPool, MemberInterestShare


@transaction.atomic
def distribute_interest(year, performed_by=None):

    # 🔒 Lock pool
    pool = YearlyInterestPool.objects.select_for_update().get(year=year)

    if pool.status == YearlyInterestPool.Status.DISTRIBUTED:
        raise ValidationError("Already distributed.")

    if pool.status != YearlyInterestPool.Status.APPROVED:
        raise ValidationError("Pool must be approved first.")

    # 🔒 Lock source account
    source_account = SJP2_Account.objects.select_for_update().get(
        pk=pool.source_account_id)

    # 🏦 System Pool (clearing account)
    distribution_account = SJP2_Account.objects.filter(purpose="System Pool" ).first()

    if not distribution_account:
        raise ValidationError("System Pool account not configured.")

    # 💰 Determine distributable amount
    distributable_amount = min(pool.total_interest, source_account.balance)

    if distributable_amount <= 0:
        raise ValidationError("No funds available.")

    # 👥 Active members
    accounts = MemberAccount.objects.filter(
        status_type=MemberAccount.StatusType.ACTIVE )

    if not accounts.exists():
        raise ValidationError("No active accounts found.")

    total_principal = sum(
        (a.principal or Decimal("0.00")) for a in accounts )

    if total_principal <= 0:
        raise ValidationError("Total principal is zero.")

    # 📊 Calculate shares
    shares = []

    total_raw = Decimal("0.00")
    total_distributed = Decimal("0.00")

    for acc in accounts:
        principal = acc.principal or Decimal("0.00")
        if principal <= 0:
            continue

        ratio = principal / total_principal

        raw_interest = (ratio * distributable_amount).quantize(
            Decimal("0.01"), rounding=ROUND_DOWN
        )

        distribute_value = (raw_interest // Decimal("500")) * Decimal("500")
        not_distributed_value = raw_interest - distribute_value

        total_raw += raw_interest
        total_distributed += distribute_value

        shares.append(MemberInterestShare(
            pool=pool,
            account=acc,
            principal_snapshot=principal,
            ratio=ratio,
            interest_earned=raw_interest,
            distribute=distribute_value,
            not_distributed=not_distributed_value   ))

    if not shares:
        raise ValidationError("No valid accounts for distribution.")

    pool.total_not_distributed = sum( s.not_distributed for s in shares )
    pool.total_distributed = sum(s.distribute for s in shares)

    MemberInterestShare.objects.bulk_create(shares)

    # 📒 SINGLE SOURCE OF TRUTH TRANSACTION (IMPORTANT)  ##Amount is acceepteed by SJP2Transaction, time,....
    SJP2Transaction.objects.create(
        from_sjp2_account=source_account,
        transaction_type=SJP2Transaction.TransactionType.Interest_Distribution,
        amount=distributable_amount,
        interest_pool=pool,

        performed_by=performed_by
    )

    # 🔐 finalize pool
    pool.status = YearlyInterestPool.Status.DISTRIBUTED
    pool.total_distributed = total_distributed
    pool.total_not_distributed = pool.total_not_distributed
    pool.distributed_at = timezone.now()
    pool.distributed_by = performed_by

    pool.save(update_fields=[
        "status",
        "distributed_amount",
        "total_not_distributed",
        "distributed_at",
        "distributed_by"
    ])

    return pool
##SJP2Transaction.objects.create(
   # transaction_type=SJP2Transaction.TransactionType.Expense,
   # from_sjp2_account=source,
   # amount=Decimal("18000.00"),)