from django.urls import path
from . import views

urlpatterns = [
    path('detail/<int:id_anggota>/', views.anggota_detail, name='detail_anggota'),
    path('kelola-akun/', views.kelola_akun_view, name='kelola_akun'),
    path('tambah-admin/', views.tambah_admin, name='tambah_admin'),
    path('tambah-anggota/', views.tambah_anggota, name='tambah_anggota'),
    path('hapus-anggota/<int:id_anggota>/', views.hapus_anggota, name='hapus_anggota'),
    path('edit-anggota/<int:id_anggota>/', views.edit_anggota, name='edit_anggota'),
    path('hapus-anggota/<int:id_anggota>/', views.hapus_anggota, name='hapus_anggota'),
]
