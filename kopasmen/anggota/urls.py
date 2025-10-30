from django.urls import path
from . import views

urlpatterns = [
    path("detail/<str:nomor_anggota>/", views.detail_anggota, name="detail_anggota"),
    path('kelola-akun/', views.kelola_akun_view, name='kelola_akun'),
    path('tambah-admin/', views.tambah_admin, name='tambah_admin'),
    path('edit-admin/<int:id_admin>/', views.edit_admin, name='edit_admin'),
    path('hapus-admin/<int:id_admin>/', views.hapus_admin, name='hapus_admin'),
    path('detail-admin/<int:id_admin>/', views.detail_admin, name='detail_admin'),
    path('tambah-anggota/', views.tambah_anggota, name='tambah_anggota'),
    path('hapus-anggota/<str:nomor_anggota>/', views.hapus_anggota, name='hapus_anggota'),
    path('edit-anggota/<str:nomor_anggota>/', views.edit_anggota, name='edit_anggota'),
    path('anggota/export-excel/', views.export_excel_anggota, name='export_excel_anggota'),
    path('anggota/export-pdf/', views.export_pdf_anggota, name='export_pdf_anggota'),
    path("cek-email/", views.cek_email, name="cek_email"),
    path('upload-excel/', views.upload_excel, name='upload_excel'),
]
