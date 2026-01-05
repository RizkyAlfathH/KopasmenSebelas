from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, Q, F, Value, CharField, When, Case
from django.contrib import messages

from .forms import SimpananForm, EditSimpananForm, PenarikanForm
from .models import HistoryTabungan, Simpanan, Anggota, JenisSimpanan, Penarikan, Admin
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
from django.utils import timezone
from django.db import transaction


@transaction.atomic
def tambah_simpanan(request):
    if not request.session.get('admin_id'):
        return redirect('admin_koperasi:login')

    admin_login = get_object_or_404(Admin, pk=request.session['admin_id'])
    role = request.session.get('admin_role')
    username = request.session.get('admin_username')

    if request.method == "POST":
        form = SimpananForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            anggota = data['anggota']
            jenis_simpanan = data['jenis_simpanan']
            jumlah = data['jumlah_menyimpan']
            tanggal = data['tanggal_menyimpan']
            dana_sosial = data.get('dana_sosial') or 0

            # cek apakah sudah ada saldo aktif untuk anggota + jenis
            simpanan = Simpanan.objects.filter(
                anggota=anggota,
                jenis_simpanan=jenis_simpanan
            ).first()

            if simpanan:
                # update saldo aktif
                simpanan.jumlah_menyimpan += jumlah
                if dana_sosial:
                    simpanan.dana_sosial += dana_sosial
                simpanan.tanggal_menyimpan = tanggal  # optional, simpan terakhir kali
                simpanan.admin = admin_login
                simpanan.save()
            else:
                # buat record baru
                simpanan = Simpanan.objects.create(
                    anggota=anggota,
                    jenis_simpanan=jenis_simpanan,
                    jumlah_menyimpan=jumlah,
                    dana_sosial=dana_sosial,
                    tanggal_menyimpan=tanggal,
                    admin=admin_login
                )

            # catat transaksi di history
            HistoryTabungan.objects.create(
                anggota=anggota,
                jenis_simpanan=jenis_simpanan,
                jumlah=jumlah,
                tanggal=tanggal,
                jenis_transaksi='SETOR'
            )

            messages.success(request, "Simpanan berhasil ditambahkan.")
            return redirect('daftar_simpanan')
    else:
        form = SimpananForm()

    return render(request, "simpanan_form.html", {
        "form": form,
        "username": username,
        "role": role,
        "admin": admin_login,
    })


def autocomplete_anggota(request):
    term = request.GET.get("q", "")
    results = []

    if term:
        anggotas = Anggota.objects.filter(
            Q(nama__icontains=term) | Q(nip__icontains=term)
        )[:10]

        results = [
            {
                "id": a.pk,
                "text": f"{a.nama} ({a.nomor_anggota})"
            }
            for a in anggotas
        ]

    return JsonResponse({"results": results})


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
    if not request.session.get('admin_id'):
        return redirect('admin_koperasi:login')

    role = request.session.get('admin_role')
    username = request.session.get('admin_username')

    anggotas = Anggota.objects.all()
    data_list = []

    for anggota in anggotas:
        def get_saldo(jenis_id):
            return (
                Simpanan.objects.filter(
                    anggota=anggota,
                    jenis_simpanan__id_jenis_simpanan=jenis_id
                ).aggregate(total=Sum('jumlah_menyimpan'))['total'] or 0
            )

        total_pokok = get_saldo(1)
        total_wajib = get_saldo(2)
        total_sukarela = get_saldo(3)

        total_dana_sosial = (
            Simpanan.objects.filter(anggota=anggota)
            .aggregate(total=Sum('dana_sosial'))['total'] or 0
        )

        data_list.append({
            'kode_anggota': anggota.nomor_anggota,
            'no_anggota': anggota.nomor_anggota,
            'nama_anggota': anggota.nama,
            'total_pokok': total_pokok,
            'total_wajib': total_wajib,
            'total_sukarela': total_sukarela,
            'total_dana_sosial': total_dana_sosial,
        })

    paginator = Paginator(data_list, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "daftar_simpanan.html", {
        'username': username,
        'role': role,
        'data': page_obj,
        'page_obj': page_obj,
    })


def detail_simpanan(request, id_simpanan):
    if not request.session.get('admin_id'):
        return redirect('admin_koperasi:login')

    admin_login = get_object_or_404(Admin, pk=request.session['admin_id'])
    role = request.session.get('admin_role')
    username = request.session.get('admin_username')

    simpanan = get_object_or_404(Simpanan, id_simpanan=id_simpanan)
    anggota = simpanan.anggota
    jenis = simpanan.jenis_simpanan

    tanggal_filter = request.GET.get('tanggal')

    history = HistoryTabungan.objects.filter(
        anggota=anggota,
        jenis_simpanan=jenis
    )

    if tanggal_filter:
        history = history.filter(tanggal=tanggal_filter)

    history = history.annotate(
        nominal=F('jumlah'),
        tanggal_transaksi=F('tanggal'),
        jenis_trans=Case(
            When(jenis_transaksi='SETOR', then=Value('Setoran')),
            When(jenis_transaksi='TARIK', then=Value('Penarikan')),
            When(jenis_transaksi='KOREKSI', then=Value('Koreksi')),
            default=Value('-'),
            output_field=CharField()
        )
    ).order_by('-tanggal')

    context = {
        'simpanan': simpanan,
        'history': history,
        'saldo_jenis': simpanan.jumlah_menyimpan,  # 🔥 DARI DB
        "username": username,
        "role": role,
        "admin": admin_login,
    }
    return render(request, 'detail_simpanan.html', context)


def edit_simpanan(request, nomor_anggota):
    if not request.session.get('admin_id'):
        return redirect('admin_koperasi:login')

    admin_login = get_object_or_404(Admin, pk=request.session['admin_id'])
    username = request.session.get('admin_username')
    role = request.session.get('admin_role')

    anggota = get_object_or_404(Anggota, nomor_anggota=nomor_anggota)

    # Ambil simpanan terakhir per jenis
    simpanan_map = {}
    for jenis in ["Simpanan Pokok", "Simpanan Wajib", "Simpanan Sukarela"]:
        simpanan_map[jenis] = Simpanan.objects.filter(
            anggota=anggota,
            jenis_simpanan__nama_jenis=jenis
        ).order_by('-tanggal_menyimpan').first()

    if request.method == "POST":
        form = EditSimpananForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data

            mapping = {
                "Simpanan Pokok": cd['simpanan_pokok'],
                "Simpanan Wajib": cd['simpanan_wajib'],
                "Simpanan Sukarela": cd['simpanan_sukarela'],
            }

            ada_perubahan = False

            for jenis_nama, input_jumlah in mapping.items():
                simpanan = simpanan_map[jenis_nama]

                # kosong / None / 0 → skip
                if not input_jumlah or input_jumlah <= 0:
                    continue

                # ambil jenis
                jenis_obj = get_object_or_404(JenisSimpanan, nama_jenis=jenis_nama)

                if simpanan:
                    # ADA → cek apakah berubah
                    if simpanan.jumlah_menyimpan != input_jumlah:
                        simpanan.jumlah_menyimpan = input_jumlah
                        simpanan.tanggal_menyimpan = cd['tanggal_menyimpan']
                        simpanan.admin = admin_login
                        simpanan.save()
                        ada_perubahan = True
                else:
                    # BELUM ADA → CREATE HANYA JIKA > 0
                    Simpanan.objects.create(
                        anggota=anggota,
                        admin=admin_login,
                        jenis_simpanan=jenis_obj,
                        tanggal_menyimpan=cd['tanggal_menyimpan'],
                        jumlah_menyimpan=input_jumlah
                    )
                    ada_perubahan = True

            if ada_perubahan:
                messages.success(request, "Simpanan berhasil diperbarui.")
            else:
                messages.info(request, "Tidak ada perubahan data simpanan.")

            return redirect('simpanan_anggota', nomor_anggota=anggota.nomor_anggota)
    else:
        form = EditSimpananForm(initial={
            'tanggal_menyimpan': timezone.now().date(),
            'simpanan_pokok': simpanan_map["Simpanan Pokok"].jumlah_menyimpan if simpanan_map["Simpanan Pokok"] else '',
            'simpanan_wajib': simpanan_map["Simpanan Wajib"].jumlah_menyimpan if simpanan_map["Simpanan Wajib"] else '',
            'simpanan_sukarela': simpanan_map["Simpanan Sukarela"].jumlah_menyimpan if simpanan_map["Simpanan Sukarela"] else '',
        })

    return render(request, "edit_simpanan.html", {
        'form': form,
        'anggota': anggota,
        'username': username,
        'role': role,
    })


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
    return render(request, "daftar_simpanan.html", context)

@transaction.atomic
def tambah_penarikan(request, nomor_anggota, jenis):
    if not request.session.get('admin_id'):
        return redirect('admin_koperasi:login')

    role = request.session.get('admin_role')
    username = request.session.get('admin_username')

    anggota = get_object_or_404(Anggota, nomor_anggota=nomor_anggota)
    jenis_obj = get_object_or_404(JenisSimpanan, pk=jenis)

    if request.method == "POST":
        form = PenarikanForm(
            request.POST,
            anggota=anggota,
            jenis_simpanan=jenis_obj
        )

        if form.is_valid():
            jumlah = form.cleaned_data['jumlah_penarikan']

            simpanan = Simpanan.objects.select_for_update().filter(
                anggota=anggota,
                jenis_simpanan=jenis_obj
            ).first()

            if not simpanan:
                messages.error(request, "Saldo simpanan tidak ditemukan.")
                return redirect('simpanan_anggota', nomor_anggota)

            if jumlah > simpanan.jumlah_menyimpan:
                messages.error(request, "Saldo tidak mencukupi.")
                return redirect(request.path)

            simpanan.jumlah_menyimpan -= jumlah
            simpanan.save()

            penarikan = form.save(commit=False)
            penarikan.anggota = anggota
            penarikan.jenis_simpanan = jenis_obj
            penarikan.admin_id = request.session['admin_id']
            penarikan.save()

            HistoryTabungan.objects.create(
                anggota=anggota,
                jenis_simpanan=jenis_obj,
                jumlah=jumlah,
                tanggal=penarikan.tanggal_penarikan,
                jenis_transaksi='TARIK'
            )

            messages.success(request, "Penarikan berhasil.")
            return redirect('simpanan_anggota', nomor_anggota)

    else:
        form = PenarikanForm(
            anggota=anggota,
            jenis_simpanan=jenis_obj
        )

    simpanan = Simpanan.objects.filter(
        anggota=anggota,
        jenis_simpanan=jenis_obj
    ).first()

    saldo = simpanan.jumlah_menyimpan if simpanan else 0


    return render(request, "penarikan_form.html", {
        "form": form,
        "anggota": anggota,
        "jenis": jenis_obj,
        "saldo": saldo,
        "role": role,
        "username": username,
    })



def simpanan_anggota(request, nomor_anggota):
    if not request.session.get('admin_id'):
        return redirect('admin_koperasi:login')

    role = request.session.get('admin_role')
    username = request.session.get('admin_username')

    anggota = get_object_or_404(Anggota, nomor_anggota=nomor_anggota)
    data_saldo = []

    for jenis in JenisSimpanan.objects.all():
        simpanan = Simpanan.objects.filter(
            anggota=anggota,
            jenis_simpanan=jenis
        ).first()

        if not simpanan or simpanan.jumlah_menyimpan <= 0:
            continue

        data_saldo.append({
            'jenis': jenis.nama_jenis,
            'jenis_id': jenis.id_jenis_simpanan,
            'saldo': simpanan.jumlah_menyimpan,
            'last_simpanan': simpanan,
        })

    return render(request, "simpanan_anggota.html", {
        'username': username,
        'role': role,
        'anggota': anggota,
        'data_saldo': data_saldo,
    })


def detail_transaksi(request, id):
    if not request.session.get('admin_id'):
        return redirect('admin_koperasi:login')

    role = request.session.get('admin_role')
    username = request.session.get('admin_username')
    admin = Admin.objects.filter(id_admin=request.session['admin_id']).first()

    transaksi = get_object_or_404(HistoryTabungan, id_history=id)
    tipe = transaksi.jenis_simpanan

    return render(request, "detail_transaksi.html", {
        "username": username,
        "role": role,
        "admin": admin,
        "transaksi": transaksi,
        "tipe": tipe,
    })

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