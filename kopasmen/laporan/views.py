from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.utils.timezone import now
from django.db.models import Sum
from datetime import datetime, time
import calendar
import io
import xlsxwriter
from django.core.paginator import Paginator

from simpanan.models import Simpanan
from pinjaman.models import Pinjaman, Angsuran
from anggota.models import Anggota


# ==========================================================
# Helper: Generate Laporan Gabungan
# ==========================================================
def generate_laporan(anggota_list, akhir=None):
    laporan = []
    for idx, anggota in enumerate(anggota_list, start=1):
        # --- SIMPANAN ---
        filter_args = {"anggota": anggota}
        if akhir:
            filter_args["tanggal_menyimpan__lte"] = akhir

        pokok = Simpanan.objects.filter(**filter_args, jenis_simpanan__nama_jenis="Simpanan Pokok").aggregate(total=Sum("jumlah_menyimpan"))["total"] or 0
        wajib = Simpanan.objects.filter(**filter_args, jenis_simpanan__nama_jenis="Simpanan Wajib").aggregate(total=Sum("jumlah_menyimpan"))["total"] or 0
        sukarela = Simpanan.objects.filter(**filter_args, jenis_simpanan__nama_jenis="Simpanan Sukarela").aggregate(total=Sum("jumlah_menyimpan"))["total"] or 0
        total_simpanan = pokok + wajib + sukarela

        # --- PINJAMAN ---
        filter_pinj = {"nomor_anggota": anggota}
        if akhir:
            filter_pinj["tanggal_meminjam__lte"] = akhir

        total_reguler = total_khusus = total_barang = 0

        # Loop tiap jenis pinjaman
        for jenis in ["Reguler", "Khusus", "Barang"]:
            # Ambil pinjaman terakhir untuk jenis itu (yang masih aktif)
            pinjaman_terakhir = (
                Pinjaman.objects
                .filter(**filter_pinj, id_jenis_pinjaman__nama_jenis=jenis)
                .order_by('-tanggal_meminjam')
                .first()
            )

            if not pinjaman_terakhir:
                continue

            # Hitung total angsuran yang sudah dibayar
            jumlah_cicilan_terbayar = Angsuran.objects.filter(
                id_pinjaman=pinjaman_terakhir,
                tanggal_bayar__lte=akhir
            ).count()

            angsuran_pokok = pinjaman_terakhir.angsuran_per_bulan or 0
            total_terbayar = jumlah_cicilan_terbayar * angsuran_pokok
            sisa_pinjaman = pinjaman_terakhir.jumlah_pinjaman - total_terbayar

            # Kalau pinjaman sudah lunas, skip (anggap selesai)
            if sisa_pinjaman <= 0:
                continue

            # Hitung jasa
            if pinjaman_terakhir.id_kategori_jasa.kategori_jasa.lower() == "turunan":
                jasa_rupiah = sisa_pinjaman * (pinjaman_terakhir.jasa_persen / 100 if pinjaman_terakhir.jasa_persen else 0)
            else:
                jasa_rupiah = pinjaman_terakhir.jumlah_pinjaman * (pinjaman_terakhir.jasa_persen / 100 if pinjaman_terakhir.jasa_persen else 0)

            total_sisa = sisa_pinjaman + jasa_rupiah

            # Tambahkan ke total per jenis
            if jenis == "Reguler":
                total_reguler += total_sisa
            elif jenis == "Khusus":
                total_khusus += total_sisa
            elif jenis == "Barang":
                total_barang += total_sisa

        total_pinjaman = total_reguler + total_khusus + total_barang

        laporan.append({
            "no": idx,
            "nama": anggota.nama,
            "simpanan": {
                "pokok": pokok,
                "wajib": wajib,
                "sukarela": sukarela,
                "total": total_simpanan
            },
            "pinjaman": {
                "reguler": total_reguler,
                "khusus": total_khusus,
                "barang": total_barang,
                "total": total_pinjaman
            }
        })

    return laporan

# ==========================================================
# View: Laporan Gabungan
# ==========================================================
def laporan_gabungan(request):
    if not request.session.get('admin_id'):
        return redirect('admin_koperasi:login')

    username = request.session.get('admin_username')
    role = request.session.get('admin_role')

    # --- Ambil Parameter GET ---
    bulan = int(request.GET.get("bulan", now().month))
    tahun_bulan = int(request.GET.get("tahun", now().year))
    tahun_tahunan = int(request.GET.get("tahun_tahunan", now().year))

    tahun_range = list(range(2020, now().year + 1))
    bulan_list = list(range(1, 13))
    anggota_list = Anggota.objects.all().order_by("nama")

    # --- Filter Bulanan ---
    last_day_bulan = calendar.monthrange(tahun_bulan, bulan)[1]
    tanggal_akhir_bulan = datetime.combine(datetime(tahun_bulan, bulan, last_day_bulan), time(23, 59, 59))
    laporan_bulanan = generate_laporan(anggota_list, akhir=tanggal_akhir_bulan)
    tanggal_str_bulan = tanggal_akhir_bulan.strftime("%d %B %Y").upper()

    # --- Filter Tahunan ---
    tanggal_akhir_tahun = datetime.combine(datetime(tahun_tahunan, 12, 31), time(23, 59, 59))
    laporan_tahunan = generate_laporan(anggota_list, akhir=tanggal_akhir_tahun)
    tanggal_str_tahun = tanggal_akhir_tahun.strftime("31 DESEMBER %Y")

    paginator_bulanan = Paginator(laporan_bulanan, 10)
    paginator_tahunan = Paginator(laporan_tahunan, 10)

    page_bulanan = request.GET.get("page_bulan")
    page_tahunan = request.GET.get("page_tahun")

    laporan_bulanan = paginator_bulanan.get_page(page_bulanan)
    laporan_tahunan = paginator_tahunan.get_page(page_tahunan)

    # =======================================================
    # DOWNLOAD EXCEL
    # =======================================================
    export = request.GET.get("export")
    periode = request.GET.get("periode")

    if export == "excel":
        periode = request.GET.get("periode", "").strip().lower()

        nama_bulan_indo = [
            "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember"
        ]

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        bold_center = workbook.add_format({'bold': True, 'align': 'center'})
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#CCCCCC', 'border': 1, 'align': 'center'})
        border_fmt = workbook.add_format({'border': 1})
        money_fmt = workbook.add_format({'num_format': '#,##0', 'border': 1})

        # ===== CEK PERIODE =====
        if periode == "tahun":
            laporan = laporan_tahunan
            tanggal_str = tanggal_str_tahun
            nama_file = f"Laporan Tahun {tahun_tahunan}.xlsx"
        elif periode == "bulan":
            laporan = laporan_bulanan
            tanggal_str = tanggal_str_bulan
            nama_bulan = nama_bulan_indo[bulan]
            nama_file = f"Laporan {nama_bulan} {tahun_bulan}.xlsx"
        else:
            # Default ke bulanan biar gak error
            laporan = laporan_bulanan
            tanggal_str = tanggal_str_bulan
            nama_file = f"Laporan Bulan {nama_bulan_indo[bulan]} {tahun_bulan}.xlsx"


        # ===== SHEET SIMPANAN =====
        ws1 = workbook.add_worksheet("Simpanan")
        ws1.merge_range("A1:F1", "KOPASMEN", bold_center)
        ws1.merge_range("A2:F2", "DAFTAR SIMPANAN POKOK, WAJIB DAN SUKARELA", bold_center)
        ws1.merge_range("A3:F3", f"PER {tanggal_str}", bold_center)

        headers_simp = ["NO", "NAMA ANGGOTA", "POKOK", "WAJIB", "SUKARELA", "TOTAL"]
        for col, h in enumerate(headers_simp):
            ws1.write(4, col, h, header_fmt)

        for row_idx, row in enumerate(laporan, start=5):
            sim = row["simpanan"]
            ws1.write(row_idx, 0, row["no"], border_fmt)
            ws1.write(row_idx, 1, row["nama"], border_fmt)
            ws1.write(row_idx, 2, sim["pokok"], money_fmt)
            ws1.write(row_idx, 3, sim["wajib"], money_fmt)
            ws1.write(row_idx, 4, sim["sukarela"], money_fmt)
            ws1.write(row_idx, 5, sim["total"], money_fmt)

        ws1.set_column("A:A", 5)
        ws1.set_column("B:B", 30)
        ws1.set_column("C:F", 15)

        # ===== SHEET PINJAMAN =====
        ws2 = workbook.add_worksheet("Pinjaman")
        ws2.merge_range("A1:F1", "KOPASMEN", bold_center)
        ws2.merge_range("A2:F2", "DAFTAR SALDO PIUTANG", bold_center)
        ws2.merge_range("A3:F3", f"PER {tanggal_str}", bold_center)

        headers_pin = ["NO", "NAMA ANGGOTA", "REGULER", "KHUSUS", "BARANG", "TOTAL"]
        for col, h in enumerate(headers_pin):
            ws2.write(4, col, h, header_fmt)

        for row_idx, row in enumerate(laporan, start=5):
            pin = row["pinjaman"]
            ws2.write(row_idx, 0, row["no"], border_fmt)
            ws2.write(row_idx, 1, row["nama"], border_fmt)
            ws2.write(row_idx, 2, pin["reguler"], money_fmt)
            ws2.write(row_idx, 3, pin["khusus"], money_fmt)
            ws2.write(row_idx, 4, pin["barang"], money_fmt)
            ws2.write(row_idx, 5, pin["total"], money_fmt)

        ws2.set_column("A:A", 5)
        ws2.set_column("B:B", 30)
        ws2.set_column("C:F", 15)

        # ===== OUTPUT FILE =====
        workbook.close()
        output.seek(0)

        response = HttpResponse(
            output,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response['Content-Disposition'] = f'attachment; filename="{nama_file}"'
        return response

    # =======================================================
    # RENDER TEMPLATE
    # =======================================================
    context = {
        "username": username,
        "role": role,
        "bulan": bulan,
        "bulan_list": bulan_list,
        "tahun_bulan": tahun_bulan,
        "tahun_tahunan": tahun_tahunan,
        "tahun_range": tahun_range,
        "laporan_bulanan": laporan_bulanan,
        "laporan_tahunan": laporan_tahunan,
        "tanggal_akhir_bulan": tanggal_str_bulan,
        "tanggal_akhir_tahun": tanggal_str_tahun,
    }
    return render(request, "laporan.html", context)
