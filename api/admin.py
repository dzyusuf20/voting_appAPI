from django.contrib import admin
from django.contrib.auth import get_user_model
from .models import Kandidat, Vote

User = get_user_model()

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'username', 'is_app_admin', 'is_participant', 'admin_owner', 'must_change_password')
    list_filter = ('is_app_admin', 'is_participant')
    search_fields = ('username',)

@admin.register(Kandidat)
class KandidatAdmin(admin.ModelAdmin):
    list_display = ('id', 'nama', 'admin_owner', 'created_at')
    list_filter = ('admin_owner',)
    search_fields = ('nama',)

@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ('id', 'voter', 'kandidat', 'created_at')
    list_filter = ('kandidat__admin_owner',)
    search_fields = ('voter__username', 'kandidat__nama')
