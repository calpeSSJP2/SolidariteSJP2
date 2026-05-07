from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .models import Role

@receiver(post_migrate)
def create_roles(sender, **kwargs):    #after migrations, run create_roles”
    roles = [
        ("manager", "Manager"),
        ("auditor", "Auditor"),
        ("ordinary_member", "Ordinary  Member"),
        ("officer", "Officer"),
        ("verifier", "Verifier"),
        ("secretary", "Secretary"),
        ("itadmin", "IT Admin"),
    ]

    for value, label in roles:
        Role.objects.get_or_create(
            name=value,
            defaults={"description": label}
        )
#after any migration, it fires a signal called post_migrate
###Any function listening to that signal gets executed