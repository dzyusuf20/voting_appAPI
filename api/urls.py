# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import list_peserta_admin, delete_peserta

# import langsung dari module views lokal (pastikan list_peserta_admin ada di .views)
from .views import (
    register_admin, me, change_password,
    generate_peserta,
    KandidatViewSet,
    vote, hasil,
    list_peserta_admin,   # <-- tambahkan ini
    delete_peserta,
)

router = DefaultRouter()
router.register(r'kandidat', KandidatViewSet, basename='kandidat')

urlpatterns = [
    # Auth (JWT)
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Me & password
    path('me/', me, name='me'),
    path('change-password/', change_password, name='change-password'),

    # Admin ops
    path('register-admin/', register_admin, name='register-admin'),
    path('generate-peserta/', generate_peserta, name='generate-peserta'),

    # Voting & hasil
    path('vote/', vote, name='vote'),
    path('hasil/', hasil, name='hasil'),

    # Kandidat CRUD (router)
    path('', include(router.urls)),

    # Peserta list (khusus admin) — gunakan function view yang sudah ada
    path('peserta/', list_peserta_admin, name='peserta-list'),

    path('peserta/<int:id>/', delete_peserta, name='peserta-delete'),

]
