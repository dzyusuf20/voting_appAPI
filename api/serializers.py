from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.validators import RegexValidator
from django.utils.timezone import localtime
from .models import Kandidat, Vote

User = get_user_model()


# ========================
# Auth & User Serializers
# ========================

class RegisterAdminSerializer(serializers.Serializer):
    username = serializers.CharField(
        max_length=150,
        validators=[RegexValidator(r'^[\w.@+-]+$', message="Hanya huruf, angka, dan @/./+/-/_")]
    )
    password = serializers.CharField(write_only=True, validators=[validate_password])

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            is_app_admin=True,
            is_participant=False
        )


class GeneratePesertaSerializer(serializers.Serializer):
    jumlah = serializers.IntegerField(min_value=1, max_value=500)
    prefix = serializers.CharField(max_length=30, required=False, allow_blank=True)


class ChangePasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    
    # Optional: validasi tambahan bisa ditambahkan di sini jika diperlukan
    def validate(self, data):
        # request.user bisa diakses dari context jika dikirim dari view
        # user = self.context.get('request')
        return data


class MeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'is_app_admin', 'is_participant', 'must_change_password']


# ========================
# Peserta Serializer
# ========================

# Ini adalah serializer yang digunakan oleh view `list_peserta_admin`
class PesertaSerializer(serializers.ModelSerializer):
    sudah_vote = serializers.SerializerMethodField()
    date_joined = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'must_change_password', 'date_joined', 'sudah_vote']

    def get_sudah_vote(self, obj):
        # Mengecek apakah ada record Vote yang berelasi dengan user ini
        return Vote.objects.filter(voter=obj).exists()

    def get_date_joined(self, obj):
        # Mengambil dan memformat waktu sesuai zona waktu lokal server
        return localtime(obj.date_joined).strftime("%Y-%m-%d %H:%M:%S")


# ========================
# Kandidat & Vote Serializers
# ========================

class KandidatCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Kandidat
        fields = ['id', 'nama', 'visi', 'misi', 'foto_url']


class KandidatListSerializer(serializers.ModelSerializer):
    total_votes = serializers.IntegerField(read_only=True, source='votes__count')

    class Meta:
        model = Kandidat
        fields = ['id', 'nama', 'visi', 'misi', 'foto_url', 'total_votes', 'created_at']


class VoteCreateSerializer(serializers.Serializer):
    kandidat_id = serializers.IntegerField()