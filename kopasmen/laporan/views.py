from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.utils.timezone import now
from django.db.models import Sum
from datetime import datetime, time
import calendar

from simpanan.models import Simpanan
from pinjaman.models import Pinjaman, Angsuran
from anggota.models import Anggota

# === Library Export ===
import io
import xlsxwriter
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER

# ================================================
# Helper Function: Generate Laporan Gabungan
# ================================================
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

        for jenis in ["Reguler", "Khusus", "Barang"]:
            pinjaman_qs = Pinjaman.objects.filter(**filter_pinj, id_jenis_pinjaman__nama_jenis=jenis)
            for pin in pinjaman_qs:
                angsuran_pokok = pin.angsuran_per_bulan or 0
                jumlah_cicilan_terbayar = Angsuran.objects.filter(id_pinjaman=pin, tanggal_bayar__lte=akhir).count()
                sisa_pinjaman = pin.jumlah_pinjaman - (jumlah_cicilan_terbayar * angsuran_pokok)
                if sisa_pinjaman < 0:
                    sisa_pinjaman = 0

                if pin.id_kategori_jasa.kategori_jasa.lower() == "turunan":
                    jasa_rupiah = sisa_pinjaman * (pin.jasa_persen / 100 if pin.jasa_persen else 0)
                else:
                    jasa_rupiah = pin.jumlah_pinjaman * (pin.jasa_persen / 100 if pin.jasa_persen else 0)

                sisa = sisa_pinjaman + jasa_rupiah

                if jenis == "Reguler":
                    total_reguler += sisa
                elif jenis == "Khusus":
                    total_khusus += sisa
                elif jenis == "Barang":
                    total_barang += sisa

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

# ================================================
# View Laporan Gabungan Bulanan & Tahunan
# ================================================
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

    # === DOWNLOAD PDF & EXCEL ===
    export = request.GET.get("export")
    periode = request.GET.get("periode", "bulan")
    if export in ["pdf", "excel"]:
        if periode == "tahun":
            laporan = laporan_tahunan
            tanggal_str = tanggal_str_tahun
        else:
            laporan = laporan_bulanan
            tanggal_str = tanggal_str_bulan

        if export == "pdf":
            # --- PDF ---
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
            elements = []
            styles = getSampleStyleSheet()
            centered = styles['Heading2']
            centered.alignment = TA_CENTER

            # Header SIMPANAN
            elements.append(Paragraph("KOPASMEN", centered))
            elements.append(Paragraph("DAFTAR SIMPANAN POKOK, WAJIB DAN SUKARELA", centered))
            elements.append(Paragraph(f"PER {tanggal_str}", centered))
            elements.append(Spacer(1, 8))  # jarak lebih rapat

            data_simp = [["NO", "NAMA ANGGOTA", "POKOK", "WAJIB", "SUKARELA", "TOTAL"]]
            for row in laporan:
                sim = row["simpanan"]
                data_simp.append([
                    row["no"],
                    row["nama"],
                    "{:,}".format(int(sim["pokok"])).replace(",", "."),
                    "{:,}".format(int(sim["wajib"])).replace(",", "."),
                    "{:,}".format(int(sim["sukarela"])).replace(",", "."),
                    "{:,}".format(int(sim["total"])).replace(",", ".")
                ])
            t1 = Table(data_simp, repeatRows=1)
            t1.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#4A2C2A")),
                ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
                ("GRID", (0,0), (-1,-1), 1, colors.black),
                ("ALIGN", (2,1), (-1,-1), "RIGHT"),
                ("ALIGN", (0,0), (-1,0), "CENTER"),
            ]))
            elements.append(t1)
            elements.append(Spacer(1, 20))

            # Header PINJAMAN
            elements.append(Paragraph("KOPASMEN", centered))
            elements.append(Paragraph("DAFTAR SALDO PIUTANG", centered))
            elements.append(Paragraph(f"PER {tanggal_str}", centered))
            elements.append(Spacer(1, 8))  # jarak lebih rapat

            data_pin = [["NO", "NAMA ANGGOTA", "REGULER", "KHUSUS", "BARANG", "TOTAL"]]
            for row in laporan:
                pin = row["pinjaman"]
                data_pin.append([
                    row["no"],
                    row["nama"],
                    "{:,}".format(int(pin["reguler"])).replace(",", "."),
                    "{:,}".format(int(pin["khusus"])).replace(",", "."),
                    "{:,}".format(int(pin["barang"])).replace(",", "."),
                    "{:,}".format(int(pin["total"])).replace(",", ".")
                ])
            t2 = Table(data_pin, repeatRows=1)
            t2.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#4A2C2A")),
                ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
                ("GRID", (0,0), (-1,-1), 1, colors.black),
                ("ALIGN", (2,1), (-1,-1), "RIGHT"),
                ("ALIGN", (0,0), (-1,0), "CENTER"),
            ]))
            elements.append(t2)

            doc.build(elements)
            buffer.seek(0)
            return HttpResponse(buffer, content_type="application/pdf")

        elif export == "excel":
            # --- EXCEL ---
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            bold_center = workbook.add_format({'bold': True, 'align': 'center'})
            header_fmt = workbook.add_format({'bold': True, 'bg_color': '#CCCCCC', 'border': 1, 'align': 'center'})
            border_fmt = workbook.add_format({'border': 1})
            money_fmt = workbook.add_format({'num_format': '#,##0', 'border': 1})

            # SHEET SIMPANAN
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

            # SHEET PINJAMAN
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

            workbook.close()
            output.seek(0)
            response = HttpResponse(output, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response['Content-Disposition'] = f'attachment; filename=laporan_{periode}.xlsx'
            return response

    # === RENDER TEMPLATE ===
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
