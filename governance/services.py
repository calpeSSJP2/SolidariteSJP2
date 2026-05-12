from django.db import transaction
from django.utils import timezone
from accounts.models import User
from .models import LeadershipTerm


from django.db import transaction
from django.utils import timezone
from accounts.models import User
from .models import LeadershipTerm


@transaction.atomic
def elect_new_leader(user, role, election):

    # 🔴 Close previous active term
    LeadershipTerm.objects.filter(
        role=role,
        is_active=True
    ).update(
        is_active=False,
        ended_on=timezone.now().date()
    )

    # 🧹 Remove role from previous holders
    User.objects.filter(roles=role).exclude(id=user.id).update()

    # 👤 Assign role to new user (correct M2M usage)
    user.roles.add(role)

    # 🏛 Create new leadership term
    LeadershipTerm.objects.create(
        user=user,
        role=role,
        election=election,
        started_on=timezone.now().date(),
        is_active=True
    )