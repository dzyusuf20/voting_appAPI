from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings

class User(AbstractUser):
    # Admin aplikasi (dibuat via /api/register-admin/)
    is_app_admin = models.BooleanField(default=False)
    # Peserta (dibuat via /api/generate-peserta/)
    is_participant = models.BooleanField(default=False)
    # Untuk peserta: admin pemilik “ruang”
    admin_owner = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='owned_participants',
        limit_choices_to={'is_app_admin': True},
        help_text="Hanya terisi untuk peserta."
    )
    # Peserta wajib ganti password saat login pertama
    must_change_password = models.BooleanField(default=False)

    def __str__(self):
        role = "admin" if self.is_app_admin else ("peserta" if self.is_participant else "user")
        return f"{self.username} ({role})"


class Kandidat(models.Model):
    admin_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='kandidat_set',
        limit_choices_to={'is_app_admin': True}
    )
    nama = models.CharField(max_length=100)
    visi = models.TextField(blank=True)
    misi = models.TextField(blank=True)
    foto_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nama} (admin: {self.admin_owner.username})"


class Vote(models.Model):
    voter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='vote_set',
        limit_choices_to={'is_participant': True}
    )
    kandidat = models.ForeignKey(Kandidat, on_delete=models.CASCADE, related_name='votes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # satu peserta hanya boleh punya satu vote total
        constraints = [
            models.UniqueConstraint(fields=['voter'], name='unique_vote_per_voter')
        ]

    def __str__(self):
        return f"{self.voter.username} -> {self.kandidat.nama}"
