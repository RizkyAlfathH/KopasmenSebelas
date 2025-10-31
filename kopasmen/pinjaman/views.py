from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum, Q
from django.core.paginator import Paginator
from pinjaman.models import Pinjaman, Angsuran
from simpanan.models import JenisSimpanan, Simpanan
from .models import Anggota, Admin
from .forms import PinjamanForm
from decimal import Decimal, InvalidOperation
from datetime import date
from django.utils.dateparse import parse_date

def pinjaman_list(request):
    if not request.session.get('admin_id'):
        return redirect('admin_koperasi:login')

    username = request.session.get('admin_username')
    role = request.session.get('admin_role')

    search_query = request.GET.get('search', '')
    sort_by = request.GET.get('sort', 'nomor')  # default sort: nomor anggota

    anggota_all = Anggota.objects.all()

    anggota_list = []
    admin_id = request.session.get("admin_id")
    admin_login = get_object_or_404(Admin, id_admin=admin_id)

    for anggota in anggota_all:
        # Ambil semua pinjaman aktif milik anggota
        pinjaman_qs = Pinjaman.objects.filter(nomor_anggota=anggota).order_by('tanggal_meminjam')

        # Jalankan auto check (sukarela ke pinjaman)
        for p in pinjaman_qs:
            cek_auto_sukarela_ke_pinjaman(p, admin_login)

        # Gabungkan pinjaman berdasarkan jenis
        pinjaman_per_jenis = {
            "Reguler": [],
            "Khusus": [],
            "Barang": [],
        }

        for p in pinjaman_qs:
            jenis = p.id_jenis_pinjaman.nama_jenis
            pinjaman_per_jenis.setdefault(jenis, []).append(p)

        # Hitung sisa per jenis (ambil dari pinjaman terakhir untuk tiap jenis)
        reguler = khusus = barang = 0

        for jenis, daftar_pinjaman in pinjaman_per_jenis.items():
            if not daftar_pinjaman:
                continue

            # Ambil pinjaman terakhir (anggap sebagai yang aktif)
            pinjaman_aktif = daftar_pinjaman[-1]
            jumlah_cicilan_terbayar = Angsuran.objects.filter(
                id_pinjaman=pinjaman_aktif, tipe_bayar="cicilan"
            ).count()

            angsuran_pokok = Decimal(pinjaman_aktif.angsuran_per_bulan or 0)
            sisa_pinjaman = Decimal(pinjaman_aktif.jumlah_pinjaman) - (jumlah_cicilan_terbayar * angsuran_pokok)
            if sisa_pinjaman < 0:
                sisa_pinjaman = Decimal(0)

            if jenis == "Reguler":
                reguler = sisa_pinjaman
            elif jenis == "Khusus":
                khusus = sisa_pinjaman
            elif jenis == "Barang":
                barang = sisa_pinjaman

        total = reguler + khusus + barang

        anggota_list.append({
            'nomor_anggota': anggota.nomor_anggota,
            'nama': anggota.nama,
            'Reguler': reguler,
            'Khusus': khusus,
            'Barang': barang,
            'total': total
        })

    # Filter pencarian
    if search_query:
        anggota_list = [
            a for a in anggota_list
            if search_query.lower() in a['nama'].lower()
            or search_query.lower() in str(a['nomor_anggota']).lower()
        ]

    # Sorting
    if sort_by == 'nama':
        anggota_list.sort(key=lambda x: x['nama'])
    elif sort_by == 'nomor':
        anggota_list.sort(key=lambda x: x['nomor_anggota'])

    # Pagination
    paginator = Paginator(anggota_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'pinjaman_list.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'sort_by': sort_by,
        'username': username,
        'role': role,
    })


def pinjaman_anggota(request, nomor_anggota=None):
    if not request.session.get('admin_id'):
        return redirect('admin_koperasi:login')

    username = request.session.get('admin_username')
    role = request.session.get('admin_role')

    anggota_data = {}
    all_pinjaman_list = []
    riwayat_pinjaman = []

    anggota_list = Anggota.objects.all()
    if nomor_anggota:
        anggota_list = anggota_list.filter(nomor_anggota=nomor_anggota)

    for anggota in anggota_list:
        pinjaman_data = {
            'nomor_anggota': anggota.nomor_anggota,
            'nama': anggota.nama,
            'tanggal_meminjam': None,
            'pinjaman_reguler_awal': 0,
            'angsuran_reguler': 0,
            'jasa_persen_reguler': 0,
            'jasa_reguler': 0,
            'total_reguler': 0,
            'sisa_reguler': 0,
            'status_reguler': '-',
            'pinjaman_reguler_id': None,
            'pinjaman_khusus_awal': 0,
            'angsuran_khusus': 0,
            'jasa_persen_khusus': 0,
            'jasa_khusus': 0,
            'total_khusus': 0,
            'sisa_khusus': 0,
            'status_khusus': '-',
            'pinjaman_khusus_id': None,
            'pinjaman_barang_awal': 0,
            'angsuran_barang': 0,
            'jasa_persen_barang': 0,
            'jasa_barang': 0,
            'total_barang': 0,
            'sisa_barang': 0,
            'status_barang': '-',
            'pinjaman_barang_id': None,
        }

        pinjaman_list_obj = Pinjaman.objects.filter(nomor_anggota=anggota).order_by('tanggal_meminjam')

        if pinjaman_list_obj.exists():
            pinjaman_data['tanggal_meminjam'] = pinjaman_list_obj.first().tanggal_meminjam

        for pinjaman in pinjaman_list_obj:
            angsuran_pokok = pinjaman.angsuran_per_bulan or 0
            jumlah_cicilan_terbayar = Angsuran.objects.filter(id_pinjaman=pinjaman, tipe_bayar="cicilan").count()
            sisa_pinjaman = pinjaman.jumlah_pinjaman - (jumlah_cicilan_terbayar * angsuran_pokok)
            if sisa_pinjaman < 0:
                sisa_pinjaman = 0

            # Update status jika lunas
            if sisa_pinjaman == 0 and pinjaman.status != "Lunas":
                pinjaman.status = "Lunas"
                pinjaman.save()

            status_pinjaman = pinjaman.status

            # Hitung jasa
            if pinjaman.id_kategori_jasa.kategori_jasa.lower() == "turunan":
                jasa_rupiah = sisa_pinjaman * (pinjaman.jasa_persen / 100 if pinjaman.jasa_persen else 0)
            else:
                jasa_rupiah = pinjaman.jumlah_pinjaman * (pinjaman.jasa_persen / 100 if pinjaman.jasa_persen else 0)

            jenis = pinjaman.id_jenis_pinjaman.nama_jenis

            if status_pinjaman == "Lunas":
                riwayat_pinjaman.append({
                    'tanggal_meminjam': pinjaman.tanggal_meminjam,
                    'jenis': jenis,
                    'jumlah_pinjaman': pinjaman.jumlah_pinjaman,
                    'angsuran': angsuran_pokok,
                    'jasa_persen': pinjaman.jasa_persen,
                    'status': "Lunas",
                    'id': pinjaman.id_pinjaman
                })
            else:
                all_pinjaman_list.append({'id': pinjaman.id_pinjaman, 'jenis': jenis})

                if jenis == 'Reguler':
                    pinjaman_data.update({
                        'pinjaman_reguler_awal': pinjaman.jumlah_pinjaman,
                        'angsuran_reguler': angsuran_pokok,
                        'jasa_persen_reguler': pinjaman.jasa_persen,
                        'jasa_reguler': round(jasa_rupiah, 2),
                        'total_reguler': round(angsuran_pokok + jasa_rupiah, 2),
                        'sisa_reguler': sisa_pinjaman,
                        'status_reguler': status_pinjaman,
                        'pinjaman_reguler_id': pinjaman.id_pinjaman
                    })
                elif jenis == 'Khusus':
                    pinjaman_data.update({
                        'pinjaman_khusus_awal': pinjaman.jumlah_pinjaman,
                        'angsuran_khusus': angsuran_pokok,
                        'jasa_persen_khusus': pinjaman.jasa_persen,
                        'jasa_khusus': round(jasa_rupiah, 2),
                        'total_khusus': round(angsuran_pokok + jasa_rupiah, 2),
                        'sisa_khusus': sisa_pinjaman,
                        'status_khusus': status_pinjaman,
                        'pinjaman_khusus_id': pinjaman.id_pinjaman
                    })
                elif jenis == 'Barang':
                    pinjaman_data.update({
                        'pinjaman_barang_awal': pinjaman.jumlah_pinjaman,
                        'angsuran_barang': angsuran_pokok,
                        'jasa_persen_barang': pinjaman.jasa_persen,
                        'jasa_barang': round(jasa_rupiah, 2),
                        'total_barang': round(angsuran_pokok + jasa_rupiah, 2),
                        'sisa_barang': sisa_pinjaman,
                        'status_barang': status_pinjaman,
                        'pinjaman_barang_id': pinjaman.id_pinjaman
                    })

        anggota_data[anggota.nomor_anggota] = pinjaman_data

    # Pilih anggota pertama untuk judul
    first_anggota = None
    if anggota_data:
        first_anggota = anggota_data[list(anggota_data.keys())[0]]

    context = {
        'anggota_data': anggota_data,
        'all_pinjaman_list': all_pinjaman_list,
        'anggota': first_anggota,
        'riwayat_pinjaman': riwayat_pinjaman,
        'username': username,
        'role': role,
    }
    return render(request, 'pinjaman_anggota.html', context)


def detail_pinjaman(request, id_pinjaman):
    if not request.session.get('admin_id'):
        return redirect('admin_koperasi:login')

    username = request.session.get('admin_username')
    role = request.session.get('admin_role')

    pinjaman = get_object_or_404(Pinjaman, id_pinjaman=id_pinjaman)
    anggota = pinjaman.nomor_anggota
    angsuran_records = Angsuran.objects.filter(id_pinjaman=pinjaman)

    total_pokok_terbayar = 0
    total_jasa_terbayar = 0

    for angsuran in angsuran_records:
        if angsuran.tipe_bayar == "cicilan":
            total_pokok_terbayar += pinjaman.angsuran_per_bulan
            total_jasa_terbayar += angsuran.jumlah_bayar - pinjaman.angsuran_per_bulan
        elif angsuran.tipe_bayar == "jasa":
            total_jasa_terbayar += angsuran.jumlah_bayar

    sisa_pinjaman = pinjaman.jumlah_pinjaman - total_pokok_terbayar
    if sisa_pinjaman < 0:
        sisa_pinjaman = 0

    # ✅ Tambahan: Jika anggota sudah punya pinjaman baru dengan jenis yang sama
    # maka pinjaman lama otomatis dianggap lunas
    pinjaman_baru = Pinjaman.objects.filter(
        nomor_anggota=anggota,
        id_jenis_pinjaman=pinjaman.id_jenis_pinjaman
    ).exclude(id_pinjaman=pinjaman.id_pinjaman).order_by('-tanggal_meminjam').first()

    if pinjaman_baru and pinjaman_baru.status != "Lunas":
        # Ada pinjaman aktif baru, maka pinjaman ini dianggap sudah selesai
        sisa_pinjaman = 0
        if pinjaman.status != "Lunas":
            pinjaman.status = "Lunas"
            pinjaman.save()

    # Update status jika memang sudah lunas
    if sisa_pinjaman == 0 and pinjaman.status != "Lunas":
        pinjaman.status = "Lunas"
        pinjaman.save()

    # Hitung jasa terbaru
    if sisa_pinjaman == 0:
        jasa_rupiah = 0
        cicilan_total = 0
    else:
        if pinjaman.id_kategori_jasa.kategori_jasa.lower() == "turunan":
            jasa_rupiah = sisa_pinjaman * (pinjaman.jasa_persen / 100 if pinjaman.jasa_persen else 0)
        else:
            jasa_rupiah = pinjaman.jumlah_pinjaman * (pinjaman.jasa_persen / 100 if pinjaman.jasa_persen else 0)
        cicilan_total = pinjaman.angsuran_per_bulan + jasa_rupiah

    total_bayar = angsuran_records.aggregate(total=Sum('jumlah_bayar'))['total'] or 0

    # Filter search
    angsuran_list = angsuran_records.order_by('-tanggal_bayar')
    search_date = request.GET.get('search_date')
    if search_date:
        angsuran_list = angsuran_list.filter(tanggal_bayar=search_date)

    # Pagination
    paginator = Paginator(angsuran_list, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'pinjaman': pinjaman,
        'nomor_anggota': anggota.nomor_anggota,
        'nama_anggota': anggota.nama,
        'tanggal_pinjam': pinjaman.tanggal_meminjam,
        'jenis_pinjaman': pinjaman.id_jenis_pinjaman.nama_jenis,
        'jasa': jasa_rupiah,
        'jasa_persen': pinjaman.jasa_persen,
        'cicilan_total': cicilan_total,
        'total_bayar': total_bayar,
        'sisa_pinjaman': sisa_pinjaman,
        'kategori_pinjaman': pinjaman.id_kategori_jasa.kategori_jasa,
        'username': username,
        'role': role,
        'page_obj': page_obj,
        'request': request,
    }
    return render(request, 'detail_pinjaman.html', context)

# Tambah Pinjaman
def tambah_pinjaman(request):
    if not request.session.get('admin_id'):
        return redirect('admin_koperasi:login')

    username = request.session.get('admin_username')
    role = request.session.get('admin_role')
    admin_id = request.session.get('admin_id')

    if request.method == "POST":
        form = PinjamanForm(request.POST)
        if form.is_valid():
            pinjaman_baru = form.save(commit=False)
            pinjaman_baru.id_admin_id = admin_id

            anggota = pinjaman_baru.nomor_anggota

            # --- Cek apakah anggota masih punya pinjaman aktif (Belum Lunas)
            pinjaman_lama = Pinjaman.objects.filter(
                nomor_anggota=anggota,
                status__in=["Belum Lunas", "Proses"]
            )

            total_sisa_lama = 0

            for p in pinjaman_lama:
                angsuran_pokok = Decimal(p.angsuran_per_bulan or 0)
                jumlah_cicilan_terbayar = Angsuran.objects.filter(
                    id_pinjaman=p, tipe_bayar="cicilan"
                ).count()
                sisa = Decimal(p.jumlah_pinjaman) - (jumlah_cicilan_terbayar * angsuran_pokok)
                if sisa < 0:
                    sisa = Decimal(0)

                # ✅ Hanya gabungkan & tandai lunas kalau jenis pinjamannya sama
                if (
                    p.id_jenis_pinjaman == pinjaman_baru.id_jenis_pinjaman
                    and sisa > 0
                ):
                    total_sisa_lama += sisa
                    p.status = "Lunas"
                    p.save()
                else:
                    # Kalau jenis beda, biarkan tetap aktif
                    continue



            # --- Gabungkan sisa lama ke pinjaman baru
            if total_sisa_lama > 0:
                pinjaman_baru.jumlah_pinjaman += total_sisa_lama
                messages.info(request, f"Sisa pinjaman lama sebesar {total_sisa_lama:,} digabung ke pinjaman baru.")

            # Hitung jasa pinjaman baru
            jasa_persen = form.cleaned_data.get('jasa_persen')
            jasa_rupiah = pinjaman_baru.jumlah_pinjaman * (jasa_persen / 100 if jasa_persen else 0)

            pinjaman_baru.jasa_rupiah = round(jasa_rupiah, 2)
            pinjaman_baru.status = "Belum Lunas"
            pinjaman_baru.save()

            messages.success(request, "Pinjaman baru berhasil ditambahkan.")
            return redirect('pinjaman_list')
    else:
        form = PinjamanForm(initial={'id_admin': admin_id})

    return render(request, 'pinjaman_form.html', {
        'form': form,
        'username': username,
        'role': role,
        'admin_id': admin_id,
    })



# API untuk search anggota
def anggota_search(request):
    term = request.GET.get('q', '')
    anggota = Anggota.objects.filter(nama__icontains=term)[:10]
    results = []
    for a in anggota:
        results.append({
            "id": a.nomor_anggota,   # FIX: pakai primary key yg bener
            "text": f"{a.nama} ({a.nomor_anggota})"   # bisa tampil nama + nip
        })
    return JsonResponse({"results": results})

# ------------------------ BAYAR PINJAMAN ------------------------
def bayar_pinjaman(request, id_pinjaman):
    if not request.session.get('admin_id'):
        return redirect('admin_koperasi:login')

    username = request.session.get('admin_username')
    role = request.session.get('admin_role')
    pinjaman = get_object_or_404(Pinjaman, id_pinjaman=id_pinjaman)
    admin_id = request.session.get("admin_id")
    admin_login = get_object_or_404(Admin, id_admin=admin_id)

    # ---------------- Nilai dasar ----------------
    angsuran_pokok = Decimal(pinjaman.angsuran_per_bulan or 0)
    jumlah_pinjaman = Decimal(pinjaman.jumlah_pinjaman or 0)
    jasa_persen_setting = Decimal(pinjaman.jasa_persen or 0)

    jumlah_cicilan_terbayar = Angsuran.objects.filter(
        id_pinjaman=pinjaman, tipe_bayar="cicilan"
    ).count()

    sisa_pinjaman = jumlah_pinjaman - (Decimal(jumlah_cicilan_terbayar) * angsuran_pokok)
    if sisa_pinjaman < 0:
        sisa_pinjaman = Decimal("0")

    # ---------------- Hitung jasa bulan ini ----------------
    if pinjaman.id_kategori_jasa.kategori_jasa.lower() == "turunan":
        jasa_rupiah = (sisa_pinjaman * (jasa_persen_setting / Decimal("100"))) if jasa_persen_setting else Decimal("0")
    else:
        jasa_rupiah = (jumlah_pinjaman * (jasa_persen_setting / Decimal("100"))) if jasa_persen_setting else Decimal("0")

    jumlah_cicilan_total = angsuran_pokok + jasa_rupiah

    # ---------------- POST (proses pembayaran) ----------------
    if request.method == "POST":
        tanggal_bayar_raw = request.POST.get("tanggal_bayar")
        tanggal_bayar = parse_date(tanggal_bayar_raw) if tanggal_bayar_raw else None

        jumlah_dibayar_raw = request.POST.get("jumlah_dibayar")
        tipe_bayar = request.POST.get("tipe_bayar")  # cicilan / jasa
        jasa_persen_input_raw = request.POST.get("jasa_persen")

        # ---------------- Konversi input ----------------
        try:
            jumlah_dibayar = Decimal(jumlah_dibayar_raw)
        except (TypeError, ValueError, InvalidOperation):
            jumlah_dibayar = Decimal("0")

        try:
            jasa_persen_input = Decimal(jasa_persen_input_raw) if jasa_persen_input_raw else jasa_persen_setting
        except (TypeError, ValueError, InvalidOperation):
            jasa_persen_input = jasa_persen_setting

        # ---------------- Hitung jasa ulang berdasarkan input ----------------
        if pinjaman.id_kategori_jasa.kategori_jasa.lower() == "turunan":
            jasa_rupiah_current = (sisa_pinjaman * (jasa_persen_input / Decimal("100"))) if jasa_persen_input else Decimal("0")
        else:
            jasa_rupiah_current = (jumlah_pinjaman * (jasa_persen_input / Decimal("100"))) if jasa_persen_input else Decimal("0")

        angsuran_perbulan_total = angsuran_pokok + jasa_rupiah_current

        if not tanggal_bayar:
            messages.error(request, "Tanggal bayar tidak valid.")
            return redirect("bayar_pinjaman", id_pinjaman=pinjaman.id_pinjaman)

        # ---------------- PEMBAYARAN CICILAN ----------------
        if tipe_bayar == "cicilan":
            if jumlah_dibayar < angsuran_perbulan_total:
                messages.error(request, f"Minimal bayar untuk 1 bulan adalah {angsuran_perbulan_total:,}.")
                return redirect("bayar_pinjaman", id_pinjaman=pinjaman.id_pinjaman)

            # Catat 1 bulan cicilan
            Angsuran.objects.create(
                id_pinjaman=pinjaman,
                id_admin=admin_login,
                tanggal_bayar=tanggal_bayar,
                jumlah_bayar=angsuran_perbulan_total,
                tipe_bayar="cicilan"
            )

            # Kelebihan → masuk Simpanan Sukarela
            kelebihan = jumlah_dibayar - angsuran_perbulan_total
            if kelebihan > 0:
                try:
                    jenis_sukarela = JenisSimpanan.objects.get(nama_jenis__iexact="Simpanan Sukarela")
                except JenisSimpanan.DoesNotExist:
                    jenis_sukarela = JenisSimpanan.objects.create(nama_jenis="Simpanan Sukarela")

                Simpanan.objects.create(
                    anggota=pinjaman.nomor_anggota,
                    admin=admin_login,
                    jenis_simpanan=jenis_sukarela,
                    tanggal_menyimpan=tanggal_bayar,
                    jumlah_menyimpan=kelebihan
                )

        # ---------------- PEMBAYARAN JASA ----------------
        elif tipe_bayar == "jasa":
            if jumlah_dibayar > jasa_rupiah_current:
                messages.error(request, "Jumlah bayar jasa tidak boleh melebihi nilai jasa bulan ini.")
                return redirect("bayar_pinjaman", id_pinjaman=pinjaman.id_pinjaman)

            Angsuran.objects.create(
                id_pinjaman=pinjaman,
                id_admin=admin_login,
                tanggal_bayar=tanggal_bayar,
                jumlah_bayar=jumlah_dibayar,
                tipe_bayar="jasa"
            )

        # ---------------- UPDATE STATUS PINJAMAN ----------------
        total_cicilan_terbayar = Angsuran.objects.filter(
            id_pinjaman=pinjaman, tipe_bayar="cicilan"
        ).count()
        sisa_akhir = jumlah_pinjaman - (Decimal(total_cicilan_terbayar) * angsuran_pokok)
        if sisa_akhir <= 0:
            pinjaman.status = "Lunas"
            pinjaman.save()

        messages.success(request, "Pembayaran berhasil dicatat.")
        return redirect("pinjaman_list")

    # ---------------- GET render ----------------
    return render(request, "bayar_pinjaman.html", {
        "pinjaman": pinjaman,
        "total_bayar": Angsuran.objects.filter(id_pinjaman=pinjaman).aggregate(total=Sum('jumlah_bayar'))['total'] or Decimal("0"),
        "sisa_pinjaman": sisa_pinjaman,
        "angsuran_pokok": angsuran_pokok,
        "jasa_rupiah": jasa_rupiah.quantize(Decimal('0.01')),
        "jumlah_cicilan_total": jumlah_cicilan_total.quantize(Decimal('0.01')),
        "admin_login": admin_login,
        "username": username,
        "role": role,
    })


# ------------------------ CEK AUTO SUKARELA KE PINJAMAN ------------------------
def cek_auto_sukarela_ke_pinjaman(pinjaman, admin_login):
    """Cek dan otomatis pakai saldo Sukarela untuk bayar cicilan bulan ini"""
    today = date.today()
    bulan_ini = today.month
    tahun_ini = today.year

    # >>> Tambahan ini supaya pinjaman baru bulan ini tidak langsung auto bayar <<<
    if pinjaman.tanggal_meminjam.month == bulan_ini and pinjaman.tanggal_meminjam.year == tahun_ini:
        return  # pinjaman baru bulan ini, skip auto pembayaran

    angsuran_pokok = Decimal(pinjaman.angsuran_per_bulan or 0)
    jasa_persen = Decimal(pinjaman.jasa_persen or 0)

    # Hitung sisa pinjaman
    cicilan_terbayar = Angsuran.objects.filter(
        id_pinjaman=pinjaman, tipe_bayar="cicilan"
    ).count()
    sisa_pinjaman = Decimal(pinjaman.jumlah_pinjaman) - (cicilan_terbayar * angsuran_pokok)
    if sisa_pinjaman <= 0:
        return  # Sudah lunas

    # Hitung jasa bulan ini
    if pinjaman.id_kategori_jasa.kategori_jasa.lower() == "turunan":
        jasa_rupiah = sisa_pinjaman * (jasa_persen / Decimal("100"))
    else:
        jasa_rupiah = Decimal(pinjaman.jumlah_pinjaman) * (jasa_persen / Decimal("100"))

    total_bulan_ini = angsuran_pokok + jasa_rupiah

    # Cek apakah cicilan bulan ini sudah dicatat
    sudah_bayar_bulan_ini = Angsuran.objects.filter(
        id_pinjaman=pinjaman,
        tanggal_bayar__month=bulan_ini,
        tanggal_bayar__year=tahun_ini,
        tipe_bayar="cicilan"
    ).exists()

    if sudah_bayar_bulan_ini:
        return  # Sudah dicatat, tidak perlu auto bayar

    # Ambil saldo sukarela
    saldo_sukarela = Simpanan.objects.filter(
        anggota=pinjaman.nomor_anggota,
        jenis_simpanan__nama_jenis__iexact="Simpanan Sukarela"
    ).aggregate(total=Sum("jumlah_menyimpan"))["total"] or Decimal("0")

    if saldo_sukarela >= total_bulan_ini:
        # Ambil object jenis sukarela
        try:
            jenis_sukarela = JenisSimpanan.objects.get(nama_jenis__iexact="Simpanan Sukarela")
        except JenisSimpanan.DoesNotExist:
            jenis_sukarela = JenisSimpanan.objects.create(nama_jenis="Simpanan Sukarela")

        # Kurangi saldo sukarela
        Simpanan.objects.create(
            anggota=pinjaman.nomor_anggota,
            admin=admin_login,
            jenis_simpanan=jenis_sukarela,
            tanggal_menyimpan=today,
            jumlah_menyimpan=-total_bulan_ini
        )

        # Catat cicilan otomatis
        Angsuran.objects.create(
            id_pinjaman=pinjaman,
            id_admin=admin_login,
            tanggal_bayar=today,
            jumlah_bayar=total_bulan_ini,
            tipe_bayar="cicilan"
        )

def detail_pembayaran(request, pembayaran_id):
    if not request.session.get('admin_id'):
        return redirect('admin_koperasi:login')

    username = request.session.get('admin_username')
    role = request.session.get('admin_role')

    # Ambil pembayaran yang dipilih
    pembayaran = get_object_or_404(Angsuran, id_pembayaran=pembayaran_id)
    pinjaman = pembayaran.id_pinjaman
    angsuran_pokok = pinjaman.angsuran_per_bulan or 0

    # Semua angsuran untuk pinjaman ini, urutkan dari yang paling awal
    semua_angsuran = Angsuran.objects.filter(id_pinjaman=pinjaman).order_by('tanggal_bayar', 'id_pembayaran')

    # Hitung sisa pinjaman sebelum dan sesudah pembayaran ini
    sisa_pinjaman = pinjaman.jumlah_pinjaman
    sisa_sebelum = sisa_pinjaman
    sisa_setelah = sisa_pinjaman

    for angsuran in semua_angsuran:
        if angsuran.id_pembayaran == pembayaran.id_pembayaran:
            sisa_sebelum = sisa_pinjaman
            # Kurangi sisa pokok kalau tipe cicilan
            if angsuran.tipe_bayar == "cicilan":
                sisa_pinjaman -= angsuran_pokok
            sisa_setelah = sisa_pinjaman
            break
        else:
            # Kurangi sisa pokok jika angsuran sebelumnya tipe cicilan
            if angsuran.tipe_bayar == "cicilan":
                sisa_pinjaman -= angsuran_pokok

    # Hitung jasa untuk pembayaran ini
    if pinjaman.id_kategori_jasa.kategori_jasa.lower() == "turunan":
        # Jasa dihitung dari sisa pinjaman sebelum pembayaran
        jasa_rupiah = sisa_sebelum * (pinjaman.jasa_persen / 100 if pinjaman.jasa_persen else 0)
    else:
        # Jasa dihitung dari total pinjaman awal
        jasa_rupiah = pinjaman.jumlah_pinjaman * (pinjaman.jasa_persen / 100 if pinjaman.jasa_persen else 0)

    # Jika tipe pembayaran hanya jasa saja, jumlah bayar adalah jasa
    if pembayaran.tipe_bayar == "jasa":
        jumlah_pembayaran = pembayaran.jumlah_bayar
    else:
        jumlah_pembayaran = angsuran_pokok + jasa_rupiah

    return render(request, 'detail_pembayaran.html', {
        'pembayaran': pembayaran,
        'sisa_sebelum': sisa_sebelum,
        'sisa_setelah': sisa_setelah,
        'jasa_rupiah': round(jasa_rupiah, 2),
        'jumlah_pembayaran': round(jumlah_pembayaran, 2),
        'username': username,
        'role': role,
    })