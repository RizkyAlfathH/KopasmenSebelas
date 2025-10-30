from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from .models import Admin
from .forms import LoginForm

# import model lain
from anggota.models import Anggota
from simpanan.models import Simpanan
from pinjaman.models import Pinjaman
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth, TruncYear
from django.utils.dateformat import DateFormat
import json
import os
from django.conf import settings

ALLOWED_ROLES = {'ketua', 'sekretaris', 'bendahara'}

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username'].strip()
            password = form.cleaned_data['password']
            try:
                admin = Admin.objects.get(username=username)
            except Admin.DoesNotExist:
                messages.error(request, "Username atau password salah.")
            else:
                if admin.role not in ALLOWED_ROLES:
                    messages.error(request, "Role tidak diperbolehkan.")
                elif admin.check_password(password):
                    request.session['admin_id'] = admin.id_admin
                    request.session['admin_username'] = admin.username
                    request.session['admin_role'] = admin.role
                    return redirect('admin_koperasi:dashboard')
                else:
                    messages.error(request, "Username atau password salah.")
    else:
        form = LoginForm()
    return render(request, 'login.html', {'form': form})


def logout_view(request):
    request.session.flush()
    messages.info(request, "Logout berhasil.")
    return redirect('admin_koperasi:login')


def dashboard_view(request):
    if not request.session.get('admin_id'):
        return redirect('admin_koperasi:login')

    role = request.session.get('admin_role')
    username = request.session.get('admin_username')

    jumlah_admin = Admin.objects.count()
    jumlah_anggota = Anggota.objects.count()
    jumlah_simpanan = Simpanan.objects.aggregate(total=Sum('jumlah_menyimpan'))['total'] or 0
    jumlah_pinjaman = Pinjaman.objects.aggregate(total=Sum('jumlah_pinjaman'))['total'] or 0

    # --- Data grafik (dipakai bendahara/ketua/sekretaris) ---
    # Tren Simpanan & Pinjaman bulanan
    simpanan_bulanan = (
        Simpanan.objects
        .annotate(bulan=TruncMonth("tanggal_menyimpan"))
        .values("bulan")
        .annotate(total=Sum("jumlah_menyimpan"))
        .order_by("bulan")
    )
    pinjaman_bulanan = (
        Pinjaman.objects
        .annotate(bulan=TruncMonth("tanggal_meminjam"))
        .values("bulan")
        .annotate(total=Sum("jumlah_pinjaman"))
        .order_by("bulan")
    )

    bulan_labels = [DateFormat(x["bulan"]).format("M Y") for x in simpanan_bulanan]
    simpanan_data = [float(x["total"] or 0) for x in simpanan_bulanan]
    pinjaman_data = [float(x["total"] or 0) for x in pinjaman_bulanan]

    # Komposisi Simpanan
    simpanan_jenis = (
        Simpanan.objects
        .values("jenis_simpanan__nama_jenis")
        .annotate(total=Sum("jumlah_menyimpan"))
    )
    simpanan_labels = [x["jenis_simpanan__nama_jenis"] for x in simpanan_jenis]
    simpanan_values = [float(x["total"] or 0) for x in simpanan_jenis]

    # Komposisi Pinjaman
    pinjaman_jenis = (
        Pinjaman.objects
        .values("id_jenis_pinjaman__nama_jenis")
        .annotate(total=Sum("jumlah_pinjaman"))
    )
    pinjaman_labels = [x["id_jenis_pinjaman__nama_jenis"] for x in pinjaman_jenis]
    pinjaman_values = [float(x["total"] or 0) for x in pinjaman_jenis]

    # Target vs Realisasi
    target_simpanan = 20000000  # contoh target tetap
    realisasi_simpanan = jumlah_simpanan

    # Pertumbuhan Anggota
    anggota_tahunan = (
        Anggota.objects
        .annotate(tahun=TruncYear("tanggal_daftar"))
        .values("tahun")
        .annotate(total=Count("nomor_anggota"))
        .order_by("tahun")
    )
    anggota_labels = [DateFormat(x["tahun"]).format("Y") for x in anggota_tahunan]
    anggota_values = [x["total"] for x in anggota_tahunan]

    context = {
        'username': username,
        'role': role,
        'jumlah_admin': jumlah_admin,
        'jumlah_anggota': jumlah_anggota,
        'jumlah_simpanan': jumlah_simpanan,
        'jumlah_pinjaman': jumlah_pinjaman,

        # Data grafik (JSON)
        "bulan_labels": json.dumps(bulan_labels),
        "simpanan_data": json.dumps(simpanan_data),
        "pinjaman_data": json.dumps(pinjaman_data),

        "simpanan_labels": json.dumps(simpanan_labels),
        "simpanan_values": json.dumps(simpanan_values),

        "pinjaman_labels": json.dumps(pinjaman_labels),
        "pinjaman_values": json.dumps(pinjaman_values),

        "target_simpanan": target_simpanan,
        "realisasi_simpanan": float(realisasi_simpanan),

        "anggota_labels": json.dumps(anggota_labels),
        "anggota_values": json.dumps(anggota_values),
    }

    if role == 'ketua':
        tpl = 'dashboard_ketua.html'
    elif role == 'sekretaris':
        tpl = 'dashboard_sekretaris.html'
    else:
        tpl = 'dashboard_bendahara.html'

    return render(request, tpl, context)

def link_callback(uri, rel):
    """
    Convert HTML URIs to absolute system paths
    """
    if uri.startswith(settings.STATIC_URL):
        path = os.path.join(settings.BASE_DIR, "static", uri.replace(settings.STATIC_URL, ""))
    elif uri.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ""))
    else:
        return uri

    if not os.path.isfile(path):
        raise Exception(f"File not found: {path}")
    return path
