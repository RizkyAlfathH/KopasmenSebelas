from django.urls import path
from .views import (
    LoginView, CheckNomorAnggotaView, ResetPasswordView,
    SimpananListView, PenarikanListView,
    PinjamanListView, AngsuranListView, ProfilAnggotaView
)

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("check-nip/", CheckNomorAnggotaView.as_view(), name="check_nip"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset_password"),
    path("<str:nip>/simpanan/", SimpananListView.as_view(), name="simpanan-list"),
    path("<str:nip>/tarik/", PenarikanListView.as_view(), name="penarikan-list"),
    path("<str:nip>/pinjaman/", PinjamanListView.as_view(), name="pinjaman-list"),
    path("profil/<str:nomor_anggota>/", ProfilAnggotaView.as_view(), name="profil-anggota"),

]