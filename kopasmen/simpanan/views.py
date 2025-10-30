from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, Q, F, Value, CharField
from django.contrib import messages
from .forms import SimpananForm, EditSimpananForm, PenarikanForm
from .models import Simpanan, Anggota, JenisSimpanan, Penarikan
from admin_koperasi.models import Admin
from django.core.paginator import Paginator
from django.db import models
from itertools import chain
from operator import attrgetter
import datetime
from django.http import JsonResponse
from django.utils.dateparse import parse_date
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from django.template.loader import get_template
from xhtml2pdf import pisa
import os
from django.conf import settings
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from num2words import num2words


def tambah_simpanan(request):
    """Tambah data simpanan baru"""
    if not request.session.get('admin_id'):
        return redirect('admin_koperasi:login')

    role = request.session.get('admin_role')
    username = request.session.get('admin_username')
    admin = Admin.objects.filter(id_admin=request.session['admin_id']).first()

    anggotas = Anggota.objects.all()  # masih dipakai kalau perlu list

    if request.method == "POST":
        form = SimpananForm(request.POST)
        if form.is_valid():
            simpanan = form.save(commit=False)
            simpanan.admin = admin  # isi otomatis dari session
            if not simpanan.tanggal_menyimpan:
                simpanan.tanggal_menyimpan = datetime.date.today()
            simpanan.save()
            messages.success(request, "Data simpanan berhasil ditambahkan.")
            return redirect("daftar_simpanan")
    else:
        form = SimpananForm(initial={
            "admin": admin,
            "tanggal_menyimpan": datetime.date.today()
        })

    context = {
        "username": username,
        "role": role,
        "admin": admin,
        "anggotas": anggotas,
        "form": form,
    }
    return render(request, "simpanan_form.html", context)

def autocomplete_anggota(request):
    term = request.GET.get("term", "")
    results = []
    if term:
        anggotas = Anggota.objects.filter(
            Q(nama__icontains=term) | Q(nip__icontains=term)
        )[:10]
        results = [
            {"id": a.pk, "nama": a.nama, "nip": a.nip}
            for a in anggotas
        ]
    return JsonResponse(results, safe=False)

def cek_dana_sosial(request, anggota_id, tanggal):
    try:
        tgl = parse_date(tanggal)  # convert string → date
        tahun = tgl.year
        bulan = tgl.month

        sudah_bayar = Simpanan.objects.filter(
            anggota__nomor_anggota=anggota_id,
            tanggal_menyimpan__year=tahun,
            tanggal_menyimpan__month=bulan,
        ).exclude(dana_sosial=0).exists()

        return JsonResponse({"sudah_bayar": sudah_bayar})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

def daftar_simpanan(request):
    """Daftar total simpanan semua anggota dengan pagination (saldo aktual)"""
    if not request.session.get('admin_id'):
        return redirect('admin_koperasi:login')

    role = request.session.get('admin_role')
    username = request.session.get('admin_username')

    admins = Admin.objects.all()
    anggotas = Anggota.objects.all()

    data_list = []
    for anggota in anggotas:
        # Hitung total simpanan per jenis
        total_pokok = (
            Simpanan.objects.filter(anggota=anggota, jenis_simpanan__id_jenis_simpanan=1)
            .aggregate(total=Sum('jumlah_menyimpan'))['total'] or 0
        )
        total_wajib = (
            Simpanan.objects.filter(anggota=anggota, jenis_simpanan__id_jenis_simpanan=2)
            .aggregate(total=Sum('jumlah_menyimpan'))['total'] or 0
        )
        total_sukarela = (
            Simpanan.objects.filter(anggota=anggota, jenis_simpanan__id_jenis_simpanan=3)
            .aggregate(total=Sum('jumlah_menyimpan'))['total'] or 0
        )

        # Dana sosial (langsung dari field dana_sosial)
        total_dana_sosial = (
            Simpanan.objects.filter(anggota=anggota)
            .aggregate(total=Sum('dana_sosial'))['total'] or 0
        )

        # Kurangi total penarikan
        total_penarikan_pokok = (
            Penarikan.objects.filter(anggota=anggota, jenis_simpanan__id_jenis_simpanan=1)
            .aggregate(total=Sum('jumlah_penarikan'))['total'] or 0
        )
        total_penarikan_wajib = (
            Penarikan.objects.filter(anggota=anggota, jenis_simpanan__id_jenis_simpanan=2)
            .aggregate(total=Sum('jumlah_penarikan'))['total'] or 0
        )
        total_penarikan_sukarela = (
            Penarikan.objects.filter(anggota=anggota, jenis_simpanan__id_jenis_simpanan=3)
            .aggregate(total=Sum('jumlah_penarikan'))['total'] or 0
        )

        data_list.append({
            'kode_anggota': anggota.nomor_anggota,
            'no_anggota': anggota.nomor_anggota,
            'nama_anggota': anggota.nama,
            'total_pokok': total_pokok - total_penarikan_pokok,
            'total_wajib': total_wajib - total_penarikan_wajib,
            'total_sukarela': total_sukarela - total_penarikan_sukarela,
            'total_dana_sosial': total_dana_sosial,  # ⬅️ tambahin ini
        })

    # Pagination per 20 data
    paginator = Paginator(data_list, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        'username': username,
        'role': role,
        'admins': admins,
        'anggotas': anggotas,
        'data': page_obj,
        'page_obj': page_obj,
    }
    return render(request, "daftar_simpanan.html", context)

def detail_simpanan(request, id_simpanan):
    """Detail simpanan anggota lengkap dengan riwayat setoran & penarikan"""
    if not request.session.get('admin_id'):
        return redirect('admin_koperasi:login')

    role = request.session.get('admin_role')
    username = request.session.get('admin_username')

    simpanan = get_object_or_404(Simpanan, id_simpanan=id_simpanan)
    anggota = simpanan.anggota
    jenis = simpanan.jenis_simpanan

    # Ambil tanggal pertama simpanan untuk jenis ini
    first_simpanan = Simpanan.objects.filter(
        anggota=anggota, jenis_simpanan=jenis
    ).order_by('tanggal_menyimpan').first()
    tanggal_tabungan = first_simpanan.tanggal_menyimpan if first_simpanan else None

    # Ambil semua setoran (dikasih pk & tipe untuk template)
    setoran_list = Simpanan.objects.filter(
        anggota=anggota, jenis_simpanan=jenis
    ).annotate(
        jenis_trans=Value('Setoran', output_field=CharField()),
        tgl=F('tanggal_menyimpan'),
        jumlah=F('jumlah_menyimpan'),
        pk=F('id_simpanan'),
        tipe=Value('simpanan', output_field=CharField())
    )

    # Ambil semua penarikan (dikasih pk & tipe untuk template)
    penarikan_list = Penarikan.objects.filter(
        anggota=anggota, jenis_simpanan=jenis
    ).annotate(
        jenis_trans=Value('Penarikan', output_field=CharField()),
        tgl=F('tanggal_penarikan'),
        jumlah=F('jumlah_penarikan'),
        pk=F('id_penarikan'),
        tipe=Value('penarikan', output_field=CharField())
    )

    # Gabungkan setoran & penarikan, urut descending
    history = sorted(
        chain(setoran_list, penarikan_list),
        key=attrgetter('tgl'),
        reverse=True
    )

    # Hitung saldo
    total_setor = sum(h.jumlah for h in setoran_list)
    total_tarik = sum(h.jumlah for h in penarikan_list)
    saldo_jenis = total_setor - total_tarik

    context = {
        'username': username,
        'role': role,
        'simpanan': simpanan,
        'saldo_jenis': saldo_jenis,
        'history': history,
        'tanggal_tabungan': tanggal_tabungan,
    }
    return render(request, "detail_simpanan.html", context)

def edit_simpanan(request, nomor_anggota):
    if not request.session.get('admin_id'):
        return redirect('admin_koperasi:login')

    role = request.session.get('admin_role')
    username = request.session.get('admin_username')

    anggota = get_object_or_404(Anggota, nomor_anggota=nomor_anggota)
    simpanan = Simpanan.objects.filter(anggota=anggota).order_by('-tanggal_menyimpan')

    # Ambil jenis simpanan dari DB
    jenis_pokok = get_object_or_404(JenisSimpanan, nama_jenis="Simpanan Pokok")
    jenis_wajib = get_object_or_404(JenisSimpanan, nama_jenis="Simpanan Wajib")
    jenis_sukarela = get_object_or_404(JenisSimpanan, nama_jenis="Simpanan Sukarela")

    if request.method == "POST":
        form = EditSimpananForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data

            if cd['simpanan_pokok']:
                Simpanan.objects.create(
                    anggota=anggota,
                    admin=cd['admin'],
                    jenis_simpanan=jenis_pokok,
                    tanggal_menyimpan=cd['tanggal_menyimpan'],
                    jumlah_menyimpan=cd['simpanan_pokok'],
                )

            if cd['simpanan_wajib']:
                Simpanan.objects.create(
                    anggota=anggota,
                    admin=cd['admin'],
                    jenis_simpanan=jenis_wajib,
                    tanggal_menyimpan=cd['tanggal_menyimpan'],
                    jumlah_menyimpan=cd['simpanan_wajib'],
                )

            if cd['simpanan_sukarela']:
                Simpanan.objects.create(
                    anggota=anggota,
                    admin=cd['admin'],
                    jenis_simpanan=jenis_sukarela,
                    tanggal_menyimpan=cd['tanggal_menyimpan'],
                    jumlah_menyimpan=cd['simpanan_sukarela'],
                )

            # Ambil simpanan terakhir untuk redirect
            last_simpanan = Simpanan.objects.filter(anggota=anggota).order_by('-id_simpanan').first()
            messages.success(request, "Data simpanan berhasil diperbarui.")
            return redirect("detail_simpanan", id_simpanan=last_simpanan.id_simpanan)
    else:
        first_simpanan = simpanan.first()
        form = EditSimpananForm(initial={
            "anggota": anggota.pk,
            "admin": first_simpanan.admin if first_simpanan else None,
            "tanggal_menyimpan": first_simpanan.tanggal_menyimpan if first_simpanan else None,
        })

    context = {
        'username': username,
        'role': role,
        'anggota': anggota,
        'simpanan': simpanan,
        'form': form,
    }
    return render(request, "edit_simpanan.html", context)



def hapus_simpanan(request, nomor_anggota):
    """Hapus semua simpanan milik anggota"""
    if not request.session.get('admin_id'):
        return redirect('admin_koperasi:login')

    role = request.session.get('admin_role')
    username = request.session.get('admin_username')

    anggota = get_object_or_404(Anggota, nomor_anggota=nomor_anggota)
    simpanan = Simpanan.objects.filter(anggota=anggota)

    if request.method == "POST":
        count, _ = simpanan.delete()
        messages.success(request, f"{count} data simpanan untuk {anggota.nama} berhasil dihapus.")
        return redirect("daftar_simpanan")

    context = {
        'username': username,
        'role': role,
        'anggota': anggota,
        'simpanan': simpanan,
    }
    return render(request, "hapus_simpanan.html", context)

def tambah_penarikan(request, nomor_anggota, jenis):
    if not request.session.get('admin_id'):
        return redirect('admin_koperasi:login')

    role = request.session.get('admin_role')
    username = request.session.get('admin_username')

    anggota = get_object_or_404(Anggota, nomor_anggota=nomor_anggota)
    jenis_obj = get_object_or_404(JenisSimpanan, id_jenis_simpanan=jenis)

    # Hitung saldo sebelum form
    total_simpanan = (
        Simpanan.objects.filter(anggota=anggota, jenis_simpanan=jenis_obj)
        .aggregate(total=Sum("jumlah_menyimpan"))["total"] or 0
    )
    total_penarikan = (
        Penarikan.objects.filter(anggota=anggota, jenis_simpanan=jenis_obj)
        .aggregate(total=Sum("jumlah_penarikan"))["total"] or 0
    )
    saldo = total_simpanan - total_penarikan

    if request.method == "POST":
        form = PenarikanForm(request.POST)
        if form.is_valid():
            penarikan = form.save(commit=False)
            penarikan.anggota = anggota
            penarikan.jenis_simpanan = jenis_obj
            penarikan.admin = Admin.objects.filter(id_admin=request.session['admin_id']).first()

            if penarikan.jumlah_penarikan > saldo:
                messages.error(request, "Saldo tidak mencukupi untuk penarikan.")
            else:
                penarikan.save()
                messages.success(request, f"Penarikan {jenis_obj.nama_jenis} berhasil.")
                return redirect('simpanan_anggota', nomor_anggota=nomor_anggota)
        else:
            messages.error(request, "Terjadi kesalahan. Silakan periksa kembali form.")
    else:
        form = PenarikanForm(initial={
            'anggota': anggota,
            'jenis_simpanan': jenis_obj,
        })

    context = {
        'username': username,
        'role': role,
        'form': form,
        'anggota': anggota,
        'jenis': jenis_obj,
        'saldo': saldo,  # kirim saldo ke template
    }
    return render(request, 'penarikan_form.html', context)

def simpanan_anggota(request, nomor_anggota):
    if not request.session.get('admin_id'):
        return redirect('admin_koperasi:login')

    role = request.session.get('admin_role')
    username = request.session.get('admin_username')

    anggota = get_object_or_404(Anggota, nomor_anggota=nomor_anggota)

    data_saldo = []
    jenis_semua = JenisSimpanan.objects.all()  # ambil semua jenis dari master

    for jenis in jenis_semua:
        total_simpanan = (
            Simpanan.objects.filter(anggota=anggota, jenis_simpanan=jenis)
            .aggregate(total=models.Sum("jumlah_menyimpan"))["total"] or 0
        )
        total_penarikan = (
            Penarikan.objects.filter(anggota=anggota, jenis_simpanan=jenis)
            .aggregate(total=models.Sum("jumlah_penarikan"))["total"] or 0
        )

        saldo = total_simpanan - total_penarikan

        # kalau belum ada transaksi sama sekali (setoran dan penarikan = 0), skip
        if saldo == 0 and total_simpanan == 0 and total_penarikan == 0:
            continue

        last_simpanan = Simpanan.objects.filter(
            anggota=anggota, jenis_simpanan=jenis
        ).order_by('-tanggal_menyimpan').first()

        data_saldo.append({
            'jenis': jenis.nama_jenis,
            'jenis_id': jenis.id_jenis_simpanan,
            'saldo': saldo,
            'last_simpanan': last_simpanan,
        })

    context = {
        'username': username,
        'role': role,
        'anggota': anggota,
        'data_saldo': data_saldo,
    }
    return render(request, "simpanan_anggota.html", context)

def detail_transaksi(request, id):
    transaksi = get_object_or_404(Simpanan, id_simpanan=id)
    return render(request, "detail_transaksi.html", {"transaksi": transaksi})

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


def download_kwitansi(request, tipe, pk):
    if tipe == "simpanan":
        transaksi = get_object_or_404(Simpanan, id_simpanan=pk)
        jenis_trans = "Setoran"
        tanggal = transaksi.tanggal_menyimpan
        jumlah = transaksi.jumlah_menyimpan
        anggota = transaksi.anggota
        jenis_simpanan = transaksi.jenis_simpanan
    else:
        transaksi = get_object_or_404(Penarikan, id_penarikan=pk)
        jenis_trans = "Penarikan"
        tanggal = transaksi.tanggal_penarikan
        jumlah = transaksi.jumlah_penarikan
        anggota = transaksi.anggota
        jenis_simpanan = transaksi.jenis_simpanan

    # Response PDF
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename=\"kwitansi_{tipe}_{pk}.pdf\"'

    # Ukuran kwitansi (20.1 cm × 10.7 cm)
    width, height = (20.1*cm, 10.7*cm)
    c = canvas.Canvas(response, pagesize=(width, height))

    # ========================= HEADER ========================= #
    # Logo kiri
    try:
        c.drawImage("static/images/logo_kopasmen.jpg", 0.6*cm, height-2.5*cm,
                    width=2.2*cm, height=2.2*cm,
                    preserveAspectRatio=True, mask='auto')
    except:
        pass  # kalau logo ga ketemu, skip aja

    # Nama koperasi
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(width/2.9, height-0.9*cm,
                        "K P R I SMK NEGERI 11 KOTA BANDUNG")

    c.setFont("Helvetica", 9)
    c.drawCentredString(width/3, height-1.2*cm, "( K O P A S M E N )")

    c.setFont("Helvetica", 8)
    c.drawCentredString(width/2.8, height-1.8*cm, "Jl. Budi Cilember Telp. 6652442 Bandung")
    c.drawCentredString(width/2.8, height-2.1*cm, "HAK BADAN HUKUM NO.: 9749/BH/KWK-10/21")
    c.drawCentredString(width/2.8, height-2.4*cm, "TANGGAL : 18 NOVEMBER 1991")

    # Judul kanan
    c.setFont("Helvetica-Bold", 11)
    judul = "BUKTI PENERIMAAN KAS" if jenis_trans == "Setoran" else "BUKTI PENGELUARAN KAS"
    c.drawRightString(width-0.7*cm, height-0.9*cm, judul)

    # Tambahan UNIT & K.M. NO. sejajar kiri judul
    c.setFont("Helvetica", 10)
    x_pos = width-5.5*cm   # kira-kira start biar sejajar dengan awal judul
    c.drawString(x_pos, height-1.4*cm, "UNIT:")
    c.drawString(x_pos, height-1.9*cm, "K.M. NO. ............................")



    c.setLineWidth(2)
    c.line(0.5*cm, height-2.7*cm, width/1.9, height-2.7*cm)

    # ========================= ISI =======================
    c.setFont("Helvetica", 10)

    # Nama pihak
    if jenis_trans == "Setoran":
        c.drawString(1*cm, height-3.4*cm, "Diterima dari :")  # naik 0.8 cm
    else:
        c.drawString(1*cm, height-3.4*cm, "Diberikan kepada :")

    c.setDash(1, 2)
    c.line(4*cm, height-3.6*cm, width*0.70, height-3.6*cm)  # naik 0.8 cm
    c.setDash()

    # Jumlah
    

# Jumlah
    c.drawString(1*cm, height-4.7*cm, "Jumlah        : Rp")

    # Hitung lebar kotak
    box_width_num = 4*cm      # kotak angka lebih kecil
    box_width_txt = (width*0.70)-4.5*cm - box_width_num - 0.5*cm  # sisanya buat huruf

    # Kotak kiri (angka)
    c.rect(4*cm, height-5.2*cm, box_width_num, 0.8*cm)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(4*cm + box_width_num/2, height-4.9*cm,
                        f"{int(jumlah):,}".replace(",", "."))

    # Konversi ke huruf
    terbilang = num2words(int(jumlah), lang='id')  # pastikan integer
    terbilang = terbilang.replace("nol", "").strip().capitalize()

    # Kotak kanan (huruf)
    c.rect(4*cm + box_width_num + 0.5*cm, height-5.2*cm, box_width_txt, 0.8*cm)
    c.setFont("Helvetica", 8)
    c.drawString(5*cm + box_width_num + 0.7*cm, height-4.9*cm,
                f"{terbilang} rupiah")

    # Untuk
    c.setFont("Helvetica", 11)  # lebih besar & tebal
    c.drawString(1*cm, height-6.0*cm, "Untuk         :")
    c.setFont("Helvetica", 10)  # balikin font normal buat teks lain

    c.setDash(1, 2)
    c.line(4*cm, height-6.2*cm, width*0.70, height-6.2*cm)
    c.line(1*cm, height-6.8*cm, width*0.70, height-6.8*cm)
    c.setDash()

    # ========================= FOOTER =========================
    c.setFont("Helvetica", 9)
    c.drawRightString(width-1*cm, 2.5*cm,
                      f"Bandung, {tanggal.strftime('%d %B %Y')}")

    if jenis_trans == "Setoran":
        kiri, kanan = "Pembayar", "Bendahara"
        nama_kiri, nama_kanan = f"({anggota.nama})", "(...................)"
    else:
        kiri, kanan = "Bendahara", "Penerima"
        nama_kiri, nama_kanan = "(...................)", f"({anggota.nama})"

    # Label tanda tangan
    c.drawString(2*cm, 2.0*cm, nama_kiri)
    c.drawString(2*cm, 1.5*cm, kiri)
    c.drawString(width-6*cm, 2.0*cm, nama_kanan)
    c.drawString(width-6*cm, 1.5*cm, kanan)

    # ========================= SELESAI =========================
    c.save()
    return response