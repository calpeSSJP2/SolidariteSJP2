from django.db import transaction
from django.utils import timezone
from accounts.models import User
from .models import LeadershipTerm


@transaction.atomic
def elect_new_leader(user: User, role: str, election):
    """
    Elect a new leader for a specific role.
    - Closes previous term
    - Downgrades old user
    - Assigns new role
    - Creates leadership term
    """

    # 🔎 Find previous active leader for this role
    previous_term = (
        LeadershipTerm.objects
        .filter(role=role, is_active=True)
        .select_related("user")
        .first()
    )

    if previous_term:
        old_user = previous_term.user

        # Close old leadership term
        previous_term.is_active = False
        previous_term.ended_on = timezone.now().date()
        previous_term.save(update_fields=["is_active", "ended_on"])

        # Downgrade old user
        old_user.role = User.Role.CUSTOMER
        old_user.save(update_fields=["role"])

    # 🏆 Assign new role
    user.role = role
    user.save(update_fields=["role"])

    # 🏛 Create new leadership term
    LeadershipTerm.objects.create(
        user=user,
        role=role,
        election=election,
        started_on=timezone.now().date(),
        is_active=True
    )