# accounts/context_processors.py  ,context_processor ins in settings , Temp

def user_roles(request):
    if request.user.is_authenticated:
        return {
            "user_roles": set(
                request.user.roles.values_list("name", flat=True)
            )
        }
    return {"user_roles": set()}