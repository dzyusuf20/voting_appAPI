import random, string
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils.timezone import localtime
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination # 1. IMPORT PAGINATOR
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


# -------- Auth / Users --------
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
    ser = ChangePasswordSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    user = request.user
    user.set_password(ser.validated_data['new_password'])
    if getattr(user, 'is_participant', False) and user.must_change_password:
        user.must_change_password = False
    user.save()
    return Response({"message": "Password updated"}, status=200)


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
        )
        u.must_change_password = True
        u.save(update_fields=['must_change_password'])
        accounts.append({"username": username, "password": password})

    return Response({"accounts": accounts}, status=201)


# views.py

# -------- Peserta --------
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAppAdmin])
def list_peserta_admin(request):
    """
    Admin lihat peserta yang dia buat sendiri,
    lengkap dengan tanggal dibuat dan apakah sudah vote.
    Bisa difilter dengan ?sudah_vote=true / false.
    Pagination aktif: gunakan ?page=2 (PAGE_SIZE dari settings.py)
    """
    # Ambil parameter filter dari URL
    status_vote_raw = request.query_params.get('sudah_vote', None)  # 'true' / 'false' / None
    status_vote = status_vote_raw.lower() if status_vote_raw is not None else None

    # Query peserta milik admin + anotasi 'sudah_vote' agar efisien dan bisa dipaginate
    peserta_qs = (
        User.objects
        .filter(is_participant=True, admin_owner=request.user)
        .annotate(sudah_vote=Exists(Vote.objects.filter(voter=OuterRef('pk'))))
        .order_by('date_joined')
    )

    # Terapkan filter berdasarkan sudah_vote (sebelum pagination agar paging akurat)
    if status_vote == 'true':
        peserta_qs = peserta_qs.filter(sudah_vote=True)
    elif status_vote == 'false':
        peserta_qs = peserta_qs.filter(sudah_vote=False)

    # Inisiasi paginator
    paginator = PageNumberPagination()
    page_qs = paginator.paginate_queryset(peserta_qs, request)

    # Bangun payload hasil
    data = []
    for p in page_qs:
        data.append({
            "id": p.id,
            "username": p.username,
            "must_change_password": p.must_change_password,
            "date_joined": localtime(p.date_joined).strftime("%Y-%m-%d %H:%M:%S"),
            "sudah_vote": bool(getattr(p, "sudah_vote", False)),
        })

    return paginator.get_paginated_response(data)


# -------- DELETE Peserta --------
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsAppAdmin])
def delete_peserta(request, id):
    """
    DELETE /api/peserta/<id>/
    Hanya admin bisa hapus peserta yang dia miliki.
    """
    admin = request.user

    try:
        peserta = User.objects.get(id=id, is_participant=True)
    except User.DoesNotExist:
        return Response({"error": "Peserta tidak ditemukan."}, status=404)

    if peserta.admin_owner_id != admin.id:
        return Response({"error": "Forbidden: peserta bukan milik admin ini."}, status=403)

    peserta.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)

# -------- Kandidat --------
class KandidatViewSet(viewsets.ModelViewSet):
    """
    CRUD kandidat. Data selalu TERISOLASI per admin:
    - Admin login: hanya melihat & membuat kandidat miliknya.
    - Peserta login: hanya melihat kandidat admin_owner-nya.
    - Publik (tanpa token): wajib pakai ?admin=<username_admin>.
    """
    queryset = Kandidat.objects.none()
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return KandidatListSerializer
        return KandidatCreateUpdateSerializer

    def get_queryset(self):
        user = self.request.user

        # Admin login → kandidat miliknya
        if user.is_authenticated and getattr(user, 'is_app_admin', False):
            return (Kandidat.objects
                    .filter(admin_owner=user)
                    .annotate(total_votes=Count('votes'))
                    .order_by('-created_at'))

        # Peserta login → kandidat admin_owner peserta
        if user.is_authenticated and getattr(user, 'is_participant', False):
            return (Kandidat.objects
                    .filter(admin_owner=user.admin_owner)
                    .annotate(total_votes=Count('votes'))
                    .order_by('-created_at'))

        # Publik → harus ?admin=username
        admin_username = self.request.query_params.get('admin')
        if admin_username:
            try:
                admin_user = User.objects.get(username=admin_username, is_app_admin=True)
            except User.DoesNotExist:
                return Kandidat.objects.none()
            return (Kandidat.objects
                    .filter(admin_owner=admin_user)
                    .annotate(total_votes=Count('votes'))
                    .order_by('-created_at'))

        return Kandidat.objects.none()

    def create(self, request, *args, **kwargs):
        if not (request.user.is_authenticated and request.user.is_app_admin):
            return Response({"error": "Only admin can create candidates."}, status=403)
        ser = KandidatCreateUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = ser.save(admin_owner=request.user)
        out = KandidatCreateUpdateSerializer(obj).data
        return Response(out, status=201)

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


# -------- Vote & Hasil --------
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsParticipant])
def vote(request):
    """
    Peserta vote 1x. Validasi kandidat harus milik admin yang sama.
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
    Grafik hasil PER ADMIN:
    - Admin login → hasil kandidat miliknya.
    - Peserta login → hasil kandidat admin_owner peserta.
    - Publik → ?admin=<username_admin> wajib.
    Response: [{"kandidat": "Nama", "total": 12}, ...]
    """
    user = request.user

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
