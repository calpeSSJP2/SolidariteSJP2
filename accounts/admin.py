
from django.contrib import admin
from .models import User, MembersProfile, SJP2_Profile, MemberAccount, SJP2_Account

admin.site.register(User)
admin.site.register(MembersProfile)
admin.site.register(SJP2_Profile)
admin.site.register(MemberAccount)
admin.site.register(SJP2_Account)