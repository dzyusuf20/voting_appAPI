from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.validators import RegexValidator
from .models import Kandidat, Vote

User = get_user_model()

# -------- Auth / Users --------
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


class MeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'is_app_admin', 'is_participant', 'must_change_password']


# -------- Peserta --------
class PesertaListSerializer(serializers.ModelSerializer):
    sudah_vote = serializers.SerializerMethodField()
    date_joined = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")

    class Meta:
        model = User
        fields = ['id', 'username', 'must_change_password', 'date_joined', 'sudah_vote']

    def get_sudah_vote(self, obj):
        return Vote.objects.filter(voter=obj).exists()


# -------- Kandidat / Vote --------
class KandidatCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Kandidat
        fields = ['id', 'nama', 'visi', 'misi', 'foto_url']


class KandidatListSerializer(serializers.ModelSerializer):
    total_votes = serializers.IntegerField(read_only=True)

    class Meta:
        model = Kandidat
        fields = ['id', 'nama', 'visi', 'misi', 'foto_url', 'total_votes', 'created_at']


class VoteCreateSerializer(serializers.Serializer):
    kandidat_id = serializers.IntegerField()
