from django.db import models
from anggota.models import Anggota 
from admin_koperasi.models import Admin 


class KategoriJasa(models.Model):
    id_kategori_jasa = models.BigAutoField(primary_key=True)
    kategori_jasa = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = 'Kategori_Jasa'

    def __str__(self):
        return self.kategori_jasa


class JenisPinjaman(models.Model):
    JENIS_PINJAMAN_CHOICES = [
        ('Reguler', 'Reguler'),
        ('Khusus', 'Khusus'),
        ('Barang', 'Barang'),
    ]
    
    id_jenis_pinjaman = models.BigAutoField(primary_key=True)
    nama_jenis = models.CharField(max_length=50, choices=JENIS_PINJAMAN_CHOICES)

    class Meta:
        db_table = 'Jenis_Pinjaman'

    def __str__(self):
        return self.nama_jenis


class Pinjaman(models.Model):
    id_pinjaman = models.BigAutoField(primary_key=True)
    nomor_anggota = models.ForeignKey(Anggota, on_delete=models.CASCADE)
    id_jenis_pinjaman = models.ForeignKey(JenisPinjaman, on_delete=models.CASCADE)
    id_kategori_jasa = models.ForeignKey(
        KategoriJasa,
        on_delete=models.CASCADE,
        default=1,
        db_column='id_kategori_jasa'
    )
    id_admin = models.ForeignKey(Admin, on_delete=models.CASCADE)
    jumlah_pinjaman = models.DecimalField(max_digits=18, decimal_places=2)
    angsuran_per_bulan = models.DecimalField(max_digits=18, decimal_places=2)
    jasa_persen = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    jasa_rupiah = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    tanggal_meminjam = models.DateField()
    jatuh_tempo = models.PositiveIntegerField(help_text="Lama pinjaman dalam bulan")
    sisa_pinjaman = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(max_length=20)

    class Meta:
        db_table = 'Pinjaman'

    def __str__(self):
        return f"Pinjaman {self.id_pinjaman} - {self.nomor_anggota.nama}"

    def hitung_jasa(self):
        """
        Calculate the jasa (fee) based on the loan amount and the percentage.
        """
        if self.jasa_persen and self.jumlah_pinjaman:
            return self.jumlah_pinjaman * (self.jasa_persen / 100)
        return 0

    def sisa(self):
        return self.jumlah_pinjaman - self.total_bayar()
    
class Angsuran(models.Model):
    id_pembayaran = models.BigAutoField(primary_key=True)
    id_pinjaman = models.ForeignKey(Pinjaman, on_delete=models.CASCADE)
    id_admin = models.ForeignKey(Admin, on_delete=models.CASCADE)
    jumlah_bayar = models.DecimalField(max_digits=18, decimal_places=2)
    tanggal_bayar = models.DateField()
    TIPE_BAYAR_CHOICES = (
        ("cicilan", "Cicilan + Jasa"),
        ("jasa", "Jasa Saja"),
    )
    tipe_bayar = models.CharField(max_length=10, choices=TIPE_BAYAR_CHOICES, default="cicilan")

    class Meta:
        db_table = 'Angsuran'

    def __str__(self):
        return f"Angsuran {self.id_pembayaran} - Pinjaman {self.id_pinjaman.id_pinjaman}"
