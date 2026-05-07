from django.apps import AppConfig


class Transact1RegularDepositConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'transact1_regular_deposit'

    def ready(self):
        import transact1_regular_deposit.signals  #  Important: loads the signal
