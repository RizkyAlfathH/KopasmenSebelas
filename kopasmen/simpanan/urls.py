from django.urls import path
from . import views

urlpatterns = [
    path("tambah/", views.tambah_simpanan, name="tambah_simpanan"),
    path("autocomplete/anggota/", views.autocomplete_anggota, name="autocomplete_anggota"),
    path("cek-dana-sosial/<str:anggota_id>/<str:tanggal>/", views.cek_dana_sosial, name="cek_dana_sosial"),
    path("daftar/", views.daftar_simpanan, name="daftar_simpanan"),
    path("transaksi/<int:id>/detail/", views.detail_transaksi, name="detail_transaksi"),

    # Ini tetap sama → cuma view download_kwitansi sekarang pakai ReportLab
    path("transaksi/<str:tipe>/<int:pk>/kwitansi/", views.download_kwitansi, name="download_kwitansi"),

    path("penarikan/<str:nomor_anggota>/<int:jenis>/", views.tambah_penarikan, name="tambah_penarikan"),
    path("anggota/<str:nomor_anggota>/", views.simpanan_anggota, name="simpanan_anggota"),
    path("detail/<int:id_simpanan>/", views.detail_simpanan, name="detail_simpanan"),

    # Edit / hapus berdasarkan anggota
    path("edit/<str:nomor_anggota>/", views.edit_simpanan, name="edit_simpanan"),
    path("simpanan/<str:nomor_anggota>/hapus/", views.hapus_simpanan, name="hapus_simpanan"),
]
