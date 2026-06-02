# ❌ New Mixin to enforce active status on accounts
from django.core.exceptions import ValidationError
from django.db import models

class ActiveAccountMixin(models.Model):
    class Meta:
        abstract = True

    ACCOUNT_FIELDS = []

    def check_active_accounts(self):
        for field in self.ACCOUNT_FIELDS:
            account = getattr(self, field, None)

            if account and hasattr(account, "validate_active"):
                account.validate_active()


