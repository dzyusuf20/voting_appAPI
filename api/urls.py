# api/urls.py
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views # Import semua views dari file views.py

urlpatterns = [
    # === Auth & User Management ===
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register-admin/', views.register_admin, name='register_admin'),
    path('me/', views.me, name='me'),
    path('change-password/', views.change_password, name='change_password'),

    # === Admin Actions ===
    path('generate-peserta/', views.generate_peserta, name='generate_peserta'),

    # === Peserta Management ===
    # URL untuk mendapatkan daftar semua peserta (GET)
    path('peserta/', views.list_peserta_admin, name='peserta-list'),
    
    # URL BARU: untuk satu peserta spesifik (DELETE by id)
    path('peserta/<int:pk>/', views.peserta_detail_view, name='peserta-detail'),

    # === Vote & Hasil ===
    path('vote/', views.vote, name='vote'),
    path('hasil/', views.hasil, name='hasil'),
]