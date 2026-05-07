
from .models import DepositDueTransaction
from .services import DepositDueTransactionService

from django.db.models.signals import post_save
from django.dispatch import receiver

#@receiver(post_save, sender=DepositDueTransaction)
#def process_transaction_after_save1(sender, instance, created, **kwargs):
    # Skip if save was triggered by the service itself
#  if kwargs.get("update_fields"):
 #       return

    # Skip if already processed in this cycle
   # if getattr(instance, "_processed", False):
 #       return

    # Only process real user-created or user-updated payments
  #  if not instance.is_paid and instance.amount_paid > 0 and instance.paid_on:
   #     instance._processed = True
    #    DepositDueTransactionService.calculate_and_save(instance)


#@receiver(post_save, sender=DepositDueTransaction)
#def process_transaction_after_save(sender, instance, created, **kwargs):


    # Only run if the transaction is not fully paid yet
    #if not instance.is_paid and instance.amount_paid > 0 and instance.paid_on:
        # Avoid infinite loop by checking if penalty has already been calculated
        #if instance.penalty_unpaid == 0:
         #   DepositDueTransactionService.calculate_and_save(instance)
#
