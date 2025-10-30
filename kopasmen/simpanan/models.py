from django.db import models
from anggota.models import Anggota
from admin_koperasi.models import Admin

class JenisSimpanan(models.Model):
    POKOK = "POKOK"
    WAJIB = "WAJIB"
    SUKARELA = "SUKARELA"

    JENIS_CHOICES = [
        (POKOK, "Simpanan Pokok"),
        (WAJIB, "Simpanan Wajib"),
        (SUKARELA, "Simpanan Sukarela"),
    ]

    id_jenis_simpanan = models.BigAutoField(primary_key=True)
    nama_jenis = models.CharField(
        max_length=50,
        choices=JENIS_CHOICES,
        unique=True
    )

    class Meta:
        db_table = "Jenis_Simpanan"

    def __str__(self):
        return self.get_nama_jenis_display()

class Simpanan(models.Model):
    id_simpanan = models.BigAutoField(primary_key=True)
    anggota = models.ForeignKey(Anggota, on_delete=models.CASCADE)
    admin = models.ForeignKey(Admin, on_delete=models.SET_NULL, null=True, blank=True)
    jenis_simpanan = models.ForeignKey(JenisSimpanan, on_delete=models.SET_NULL, null=True, blank=True)

    tanggal_menyimpan = models.DateField()
    tanggal_menarik = models.DateField(null=True, blank=True)
    jumlah_menyimpan = models.DecimalField(max_digits=18, decimal_places=2)

    # Tambahan field baru
    dana_sosial = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        help_text="Dana sosial yang disisihkan dari simpanan"
    )

    class Meta:
        db_table = "Simpanan"

    def __str__(self):
        return f"{self.jenis_simpanan} - {self.anggota.nama}"
    
    @staticmethod
    def sudah_bayar_dana_sosial(anggota, bulan, tahun):
        """
        Cek apakah anggota sudah bayar dana sosial di bulan & tahun tertentu
        """
        return Simpanan.objects.filter(
            anggota=anggota,
            dana_sosial__gt=0,
            tanggal_menyimpan__month=bulan,
            tanggal_menyimpan__year=tahun
        ).exists()


class Penarikan(models.Model):
    id_penarikan = models.BigAutoField(primary_key=True)
    anggota = models.ForeignKey(Anggota, on_delete=models.CASCADE)
    admin = models.ForeignKey(Admin, on_delete=models.SET_NULL, null=True, blank=True)
    jenis_simpanan = models.ForeignKey(JenisSimpanan, on_delete=models.SET_NULL, null=True, blank=True)

    jumlah_penarikan = models.DecimalField(max_digits=18, decimal_places=2)
    tanggal_penarikan = models.DateField()

    class Meta:
        db_table = "Penarikan"

    def __str__(self):
        return f"{self.jenis_simpanan} - {self.anggota.nama}"

class HistoryTabungan(models.Model):
    id_history = models.BigAutoField(primary_key=True)
    anggota = models.ForeignKey(Anggota, on_delete=models.CASCADE)
    jenis_simpanan = models.ForeignKey(JenisSimpanan, on_delete=models.SET_NULL, null=True, blank=True)
    tanggal = models.DateField()
    jenis_transaksi = models.CharField(
        max_length=10,
        choices=[('SETOR', 'Setoran'), ('TARIK', 'Penarikan')]
    )
    jumlah = models.DecimalField(max_digits=18, decimal_places=2)

    class Meta:
        db_table = "History_Tabungan"
        ordering = ['-tanggal']

    def __str__(self):
        return f"{self.anggota.nama} - {self.jenis_transaksi} Rp{self.jumlah}"
