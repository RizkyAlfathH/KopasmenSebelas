from django import forms
from admin_koperasi.models import Admin 
from .models import Anggota

class AdminForm(forms.ModelForm):
    class Meta:
        model = Admin
        fields = ['username', 'password_hash', 'role']

class AnggotaForm(forms.ModelForm):
    tanggal_daftar = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'})  # Tidak perlu menggunakan input_formats
    )

    class Meta:
        model = Anggota
        fields = '__all__'
        labels = {
            'nip': 'Nomor Induk Pegawai (NIP)',
            'nama': 'Nama',
            'alamat': 'Alamat',
            'no_telp': 'No. Telepon',
            'email': 'Email',
            'jenis_kelamin': 'Jenis Kelamin',
            'tanggal_daftar': 'Tanggal Daftar',
            'status': 'Status',
            'password_hash': 'Password',
        }