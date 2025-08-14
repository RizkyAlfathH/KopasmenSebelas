from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from datetime import datetime

class Anggota(models.Model):
    JK_CHOICES = [
        ('Laki-laki', 'Laki-laki'),
        ('Perempuan', 'Perempuan'),
    ]
    STATUS_CHOICES = [
        ('aktif', 'Aktif'),
        ('nonaktif', 'Nonaktif'),
    ]

    id_anggota = models.BigAutoField(primary_key=True)
    nip = models.CharField(max_length=30, unique=True)
    nama = models.CharField(max_length=100)
    alamat = models.CharField(max_length=255, blank=True, null=True)
    no_telp = models.CharField(max_length=20, blank=True, null=True)
    email = models.CharField(max_length=50, blank=True, null=True)
    jenis_kelamin = models.CharField(max_length=10, choices=JK_CHOICES)
    tanggal_daftar = models.DateField(default=datetime.now)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='aktif') 
    password_hash = models.CharField(max_length=255)

    class Meta:
        db_table = 'Anggota'

    def __str__(self):
        return f"{self.nip} - {self.nama}"

    def set_password(self, raw_password: str):
        
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password(raw_password, self.password_hash)
    

