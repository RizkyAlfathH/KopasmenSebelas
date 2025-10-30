from django import forms
from .models import Pinjaman, KategoriJasa, JenisPinjaman
from anggota.models import Anggota
from decimal import Decimal

class PinjamanForm(forms.ModelForm):
    class Meta:
        model = Pinjaman
        fields = [
            'nomor_anggota',
            'id_jenis_pinjaman',
            'id_kategori_jasa',
            'id_admin',
            'tanggal_meminjam',
            'jatuh_tempo',
            'jumlah_pinjaman',
            'angsuran_per_bulan',
            'jasa_persen',
            'jasa_rupiah',
        ]
        
        widgets = {
            'nomor_anggota': forms.Select(attrs={'class': 'form-control select2'}),
            'id_jenis_pinjaman': forms.Select(attrs={'class': 'form-control'}),
            'id_kategori_jasa': forms.Select(attrs={'class': 'form-control'}),
            'id_admin': forms.HiddenInput(),  # <--- BIKIN HIDDEN
            'tanggal_meminjam': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'jatuh_tempo': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 36,
                'placeholder': 'Masukkan jumlah bulan (1-36)'
            }),
            'jumlah_pinjaman': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Masukkan jumlah pinjaman'}),
            'angsuran_per_bulan': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Masukkan jumlah angsuran per bulan'}),
            'jasa_persen': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Masukkan persentase jasa'}),
            'jasa_rupiah': forms.NumberInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # supaya tidak error "This field is required."
        self.fields['id_admin'].required = False

    def clean_jasa_rupiah(self):
        cleaned_data = super().clean()
        jasa_persen = cleaned_data.get('jasa_persen')
        jumlah_pinjaman = cleaned_data.get('jumlah_pinjaman')

        if jasa_persen is not None and jumlah_pinjaman is not None:
            jasa_rupiah = jumlah_pinjaman * (jasa_persen / 100)
            return jasa_rupiah
        return 0
    
    def clean_jasa_persen(self):
        jasa_persen = self.cleaned_data.get('jasa_persen')

        if jasa_persen is None:
            return jasa_persen
        if isinstance(jasa_persen, str):
            jasa_persen = jasa_persen.replace(',', '.')

        try:
            return Decimal(jasa_persen)
        except Exception:
            raise forms.ValidationError("Persentase jasa tidak valid, gunakan format angka.")

    def clean(self):
        cleaned_data = super().clean()
        jumlah_pinjaman = cleaned_data.get('jumlah_pinjaman')
        jasa_persen = cleaned_data.get('jasa_persen')

        if jumlah_pinjaman and jasa_persen:
            jasa_rupiah = jumlah_pinjaman * (jasa_persen / Decimal(100))
            cleaned_data['jasa_rupiah'] = jasa_rupiah.quantize(Decimal('0.01'))

        cleaned_data['status'] = 'Belum Lunas'
        return cleaned_data
