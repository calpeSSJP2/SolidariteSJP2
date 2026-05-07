from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import AccountStatement, SystemAccountStatement
from accounts.models import MemberAccount, SJP2_Account


class LedgerService:

    @staticmethod
    @transaction.atomic
    def create_statement(
        account,
        transaction_type: str,
        debit=Decimal('0.00'),
        credit=Decimal('0.00'),
        reference=None,
    ):

        if debit > 0 and credit > 0:
            raise ValidationError("Only one of debit or credit allowed")

        if debit == 0 and credit == 0:
            raise ValidationError("Debit or credit required")

        delta = credit - debit

        # =========================
        # MEMBER ACCOUNT
        # =========================
        if isinstance(account, MemberAccount):

            # 🔒 LOCK ACCOUNT ROW
            account = MemberAccount.objects.select_for_update().get(pk=account.pk)

            last_stmt = (
                AccountStatement.objects
                .filter(account=account)
                .order_by('-date', '-id')
                .first()
            )
           ##Add this integrity,to forcely reconcialte if there is a mistake,  commemet temporry
            ledger_balance = last_stmt.balance_after if last_stmt else account.balance

            if account.balance != ledger_balance:
                raise RuntimeError(
                    f"Ledger mismatch for {account.account_number}: "
                    f"account.balance={account.balance}, "
                    f"ledger.balance_after={ledger_balance}"
                )

            # Apply mutation
            new_balance = (account.balance + delta).quantize(Decimal("0.01"))

            account.balance = new_balance
            account.last_activity_on = timezone.now()

            account.save(
                update_fields=['balance', 'last_activity_on'],
                **{"_from_ledger": True}
            )

            stmt = AccountStatement.objects.create(
                account=account,
                transaction_type=transaction_type,
                debit=debit,
                credit=credit,
                balance_after=new_balance,
                reference=reference,
            )

        # =========================
        # SYSTEM ACCOUNT
        # =========================
        elif isinstance(account, SJP2_Account):

            # 🔒 LOCK ACCOUNT ROW
            account = SJP2_Account.objects.select_for_update().get(pk=account.pk)

            last_stmt = (
                SystemAccountStatement.objects
                .filter(account=account)
                .order_by('-date', '-id')
                .first()
            )

            ledger_balance = last_stmt.balance_after if last_stmt else account.balance

            if account.balance != ledger_balance:
                raise RuntimeError(
                    f"Ledger mismatch for system account {account.account_nbr}: "
                    f"account.balance={account.balance}, "
                    f"ledger.balance_after={ledger_balance}"
                )

            # Apply mutation
            new_balance = (account.balance + delta).quantize(Decimal("0.01"))

            account.balance = new_balance
            account.last_activity_on = timezone.now()

            account.save(
                update_fields=['balance', 'last_activity_on'],
                **{"_from_ledger": True}
            )

            stmt = SystemAccountStatement.objects.create(
                account=account,
                transaction_type=transaction_type,
                debit=debit,
                credit=credit,
                balance_after=new_balance,
                reference=reference,
            )

        else:
            raise ValueError("Invalid account type")

        return stmt