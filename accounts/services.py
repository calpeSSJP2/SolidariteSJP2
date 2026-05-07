# accounts/services.py

from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from accounts.models import MemberAccount, SHARE_VALUE, MembersProfile, SJP2_Account
from transact1_regular_deposit.models import SJP2Transaction
from ledger.services import LedgerService


@transaction.atomic
def create_member_account_with_capital(member_profile: MembersProfile, shares: int):
    """
    Create a MemberAccount safely, record initial deposit,
    ledger entries for the member and system account.
    """

    if shares <= 0:
        raise ValueError("Number of shares must be positive")

    if MemberAccount.objects.filter(member=member_profile).exists():
        raise ValueError(f"Member {member_profile} already has an account.")

    # 1️⃣ Total contribution
    amount = SHARE_VALUE  # total contribution = share value * number of shares

    # 2️⃣ Create member account
    account = MemberAccount.objects.create(
        member=member_profile,
        shares=shares,
        initial_deposit=amount,
        #principal=amount,Yhis money canot touch principal
        opened_on=timezone.now())

    # 3️⃣ Record system transaction
    main_sjp2_account = SJP2_Account.get_main_account()
    if not main_sjp2_account:
        raise ValueError("No main SJP2 system account found!")

    transaction_record = SJP2Transaction.objects.create(
        transaction_type=SJP2Transaction.TransactionType.INITIAL_DEPOSIT,
        amount=amount,
        from_member_account=account,
        to_sjp2_account=main_sjp2_account,
        description=f"Initial capital contribution ({shares} shares)" )

    # 4️⃣ Ledger entry for member (negative effect)
    LedgerService.create_statement(
        account=account,
        transaction_type="INITIAL_DEPOSIT",
        debit=Decimal('0.00'),  # money leaving the member → shows as negative
        credit=amount,
        reference=f"MEMBER_INIT_DEPOSIT ({transaction_record.id})")
    # 4️⃣ Ledger entry for member (negative effect)
    LedgerService.create_statement(
        account=account,
        transaction_type="Transfer_membeship",
        debit=amount,  # money leaving the member → shows as negative
        credit=Decimal('0.00'),
        reference=f"MEMBER_INIT_Transfer_out ({transaction_record.id})")
    # 5️⃣ Ledger entry for system account (receives money)
    LedgerService.create_statement(
        account=main_sjp2_account,
        transaction_type="MEMBER_INITIAL_DEPOSIT",
        debit=Decimal('0.00'),
        credit=amount,  # system receives → shows as positive
        reference=f"MEMBER_INIT_DEPOSIT ({transaction_record.id})" )

    # 6️⃣ Update last activity
    #account.last_activity_on = timezone.now()
    #account.save(update_fields=['last_activity_on'])
    account.update_activity()
    return account, transaction_record

# accounts/services.py

class AccountService:
    @staticmethod
    def update_principal(account, amount):
        """Update the principal balance of a member account."""
        account.principal += amount
        account.save(update_fields=["principal"])
