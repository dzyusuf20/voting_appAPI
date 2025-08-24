import random, string
from django.contrib.auth import get_user_model
from django.db.models import Count, Exists, OuterRef
from django.shortcuts import get_object_or_404
from django.utils.timezone import localtime
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from .models import Kandidat, Vote
from .serializers import (
    RegisterAdminSerializer,
    GeneratePesertaSerializer,
    ChangePasswordSerializer,
    MeSerializer,
    KandidatCreateUpdateSerializer,
    KandidatListSerializer,
    VoteCreateSerializer,
)
from .permissions import IsAppAdmin, IsParticipant

User = get_user_model()


# ========================
# Auth / User Management
# ========================

@api_view(['POST'])
@permission_classes([AllowAny])
def register_admin(request):
    """
    Buat admin aplikasi baru (bukan superuser Django).
    """
    ser = RegisterAdminSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    user = ser.save()
    return Response({"message": "Admin created", "username": user.username}, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    """
    Info role & flag user untuk frontend (admin/peserta, must_change_password).
    """
    return Response(MeSerializer(request.user).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    Peserta atau admin ganti password sendiri.
    """
    ser = ChangePasswordSerializer(data=request.data, context={'request': request.user})
    ser.is_valid(raise_exception=True)
    user = request.user
    user.set_password(ser.validated_data['new_password'])
    if getattr(user, 'is_participant', False) and user.must_change_password:
        user.must_change_password = False
    user.save()
    return Response({"message": "Password updated"}, status=200)


# ========================
# Admin Actions
# ========================

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAppAdmin])
def generate_peserta(request):
    """
    Admin generate N peserta (username+password random) yang terikat pada admin ini.
    """
    ser = GeneratePesertaSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    jumlah = ser.validated_data['jumlah']
    prefix = ser.validated_data.get('prefix') or 'peserta'

    accounts = []
    for _ in range(jumlah):
        suffix = ''.join(random.choices(string.digits, k=5))
        username = f"{prefix}{suffix}"
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        u = User.objects.create_user(
            username=username,
            password=password,
            is_app_admin=False,
            is_participant=True,
            admin_owner=request.user,
            must_change_password=True
        )
        accounts.append({"username": username, "password": password})

    return Response({"accounts": accounts}, status=201)


# ========================
# Peserta Views
# ========================

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAppAdmin])
def list_peserta_admin(request):
    """
    Admin lihat peserta yang dia buat sendiri, dengan filter dan pagination.
    """
    status_vote_raw = request.query_params.get('sudah_vote', None)
    
    peserta_qs = User.objects.filter(is_participant=True, admin_owner=request.user)

    if status_vote_raw is not None:
        sudah_vote_bool = status_vote_raw.lower() == 'true'
        peserta_qs = peserta_qs.annotate(
            sudah_vote=Exists(Vote.objects.filter(voter=OuterRef('pk')))
        ).filter(sudah_vote=sudah_vote_bool)
    
    peserta_qs = peserta_qs.order_by('date_joined')

    paginator = PageNumberPagination()
    page_qs = paginator.paginate_queryset(peserta_qs, request)

    # Membangun data secara manual (sesuai kode asli Anda)
    data = []
    for p in page_qs:
        data.append({
            "id": p.id,
            "username": p.username,
            "must_change_password": p.must_change_password,
            "date_joined": localtime(p.date_joined).strftime("%Y-%m-%d %H:%M:%S"),
            "sudah_vote": Vote.objects.filter(voter=p).exists(),
        })

    return paginator.get_paginated_response(data)


# === VIEW BARU UNTUK FUNGSI HAPUS PESERTA (DELETE) ===
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsAppAdmin])
def peserta_detail_view(request, pk):
    """
    Admin hapus satu peserta berdasarkan ID (pk).
    """
    # Cari peserta berdasarkan ID, pastikan dia adalah peserta dan milik admin yg login
    peserta = get_object_or_404(User, pk=pk, is_participant=True, admin_owner=request.user)
    
    # Keamanan tambahan, meski query di atas sudah cukup
    if peserta.admin_owner != request.user:
        return Response({"error": "Anda tidak punya izin untuk menghapus peserta ini."}, status=403)
    
    peserta.delete()
    return Response(status=204) # 204 No Content menandakan sukses hapus


# ========================
# Kandidat Management (ViewSet)
# ========================
class KandidatViewSet(viewsets.ModelViewSet):
    """
    CRUD kandidat. Data selalu TERISOLASI per admin.
    """
    # ... (Isi KandidatViewSet Anda sama seperti sebelumnya, tidak perlu diubah) ...
    # ... saya potong agar lebih ringkas, tapi di file Anda biarkan lengkap ...
    queryset = Kandidat.objects.none()
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return KandidatListSerializer
        return KandidatCreateUpdateSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and getattr(user, 'is_app_admin', False):
            return Kandidat.objects.filter(admin_owner=user).annotate(total_votes=Count('votes')).order_by('-created_at')
        if user.is_authenticated and getattr(user, 'is_participant', False):
            return Kandidat.objects.filter(admin_owner=user.admin_owner).annotate(total_votes=Count('votes')).order_by('-created_at')
        admin_username = self.request.query_params.get('admin')
        if admin_username:
            try:
                admin_user = User.objects.get(username=admin_username, is_app_admin=True)
            except User.DoesNotExist:
                return Kandidat.objects.none()
            return Kandidat.objects.filter(admin_owner=admin_user).annotate(total_votes=Count('votes')).order_by('-created_at')
        return Kandidat.objects.none()

    def perform_create(self, serializer):
        if not (self.request.user.is_authenticated and self.request.user.is_app_admin):
            return Response({"error": "Only admin can create candidates."}, status=403)
        serializer.save(admin_owner=self.request.user)

    def update(self, request, *args, **kwargs):
        if not (request.user.is_authenticated and request.user.is_app_admin):
            return Response({"error": "Only admin can update candidates."}, status=403)
        instance = self.get_object()
        if instance.admin_owner_id != request.user.id:
            return Response({"error": "Forbidden"}, status=403)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not (request.user.is_authenticated and request.user.is_app_admin):
            return Response({"error": "Only admin can delete candidates."}, status=403)
        instance = self.get_object()
        if instance.admin_owner_id != request.user.id:
            return Response({"error": "Forbidden"}, status=403)
        return super().destroy(request, *args, **kwargs)


# ========================
# Vote & Hasil
# ========================
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsParticipant])
def vote(request):
    """
    Peserta vote 1x.
    """
    voter = request.user
    if Vote.objects.filter(voter=voter).exists():
        return Response({"error": "Anda sudah melakukan vote."}, status=400)
    ser = VoteCreateSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    kandidat_id = ser.validated_data['kandidat_id']
    try:
        kandidat = Kandidat.objects.get(id=kandidat_id)
    except Kandidat.DoesNotExist:
        return Response({"error": "Kandidat tidak ditemukan."}, status=404)
    if kandidat.admin_owner_id != voter.admin_owner_id:
        return Response({"error": "Anda tidak berhak memilih kandidat ini."}, status=403)
    Vote.objects.create(voter=voter, kandidat=kandidat)
    return Response({"message": "Vote terekam."}, status=201)


@api_view(['GET'])
@permission_classes([AllowAny])
def hasil(request):
    """
    Grafik hasil PER ADMIN.
    """
    user = request.user
    qs = Kandidat.objects.none()
    if user.is_authenticated and getattr(user, 'is_app_admin', False):
        qs = Kandidat.objects.filter(admin_owner=user)
    elif user.is_authenticated and getattr(user, 'is_participant', False):
        qs = Kandidat.objects.filter(admin_owner=user.admin_owner)
    else:
        admin_username = request.query_params.get('admin')
        if not admin_username:
            return Response({"error": "Parameter ?admin=USERNAME wajib untuk akses publik."}, status=400)
        try:
            admin_user = User.objects.get(username=admin_username, is_app_admin=True)
        except User.DoesNotExist:
            return Response([], status=200)
        qs = Kandidat.objects.filter(admin_owner=admin_user)

    data = (qs.annotate(total=Count('votes'))
              .values('nama', 'total')
              .order_by('-total', 'nama'))
    return Response([{"kandidat": r["nama"], "total": r["total"]} for r in data], status=200)