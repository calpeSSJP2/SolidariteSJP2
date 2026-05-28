# ❌ New Mixin to enforce active status on accounts
from django.core.exceptions import ValidationError
from django.db import models

class ActiveAccountMixin(models.Model):
    class Meta:
        abstract = True

    def check_active_accounts(self):
        """
        🔴 Red cross: Centralized account status check to prevent transactions on inactive accounts
        """
        accounts_to_check = []

        # 🔴 Red cross: dynamically check common account fields
        for field_name in ['account', 'source_account', 'destination_account',
                           'member_account', 'from_member_account', 'to_member_account']:
            acc = getattr(self, field_name, None)
            if acc:
                accounts_to_check.append(acc)

        for acc in accounts_to_check:
            if acc.status_type != 'active':
                raise ValidationError(
                    f"❌ Cannot perform transaction: account {acc.account_number} is {acc.status_type}")
