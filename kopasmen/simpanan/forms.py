from django import forms
from django.db.models import Sum 
from .models import Anggota, Admin, Simpanan, Penarikan
import datetime

class SimpananForm(forms.ModelForm):
    class Meta:
        model = Simpanan
        fields = ['admin', 'tanggal_menyimpan', 'anggota', 'jenis_simpanan', 'jumlah_menyimpan', 'dana_sosial']
        widgets = {
            'anggota': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'anggota-autocomplete',
                'placeholder': 'Cari anggota...'
            }),
            'admin': forms.HiddenInput(),
            'tanggal_menyimpan': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control'},
                format='%Y-%m-%d'
            ),
            'jenis_simpanan': forms.Select(attrs={'class': 'form-control'}),
            'jumlah_menyimpan': forms.NumberInput(attrs={'class': 'form-control'}),
            'dana_sosial': forms.NumberInput(attrs={'class': 'form-control', 'value': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # kalau tambah baru (belum ada instance) → isi default dengan tanggal hari ini
        if not self.instance.pk:
            self.fields['tanggal_menyimpan'].initial = datetime.date.today()


class EditSimpananForm(forms.Form):
    anggota = forms.ModelChoiceField(
        queryset=Anggota.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    admin = forms.ModelChoiceField(
        queryset=Admin.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    tanggal_menyimpan = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    simpanan_pokok = forms.IntegerField(
        required=False, widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    simpanan_wajib = forms.IntegerField(
        required=False, widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    simpanan_sukarela = forms.IntegerField(
        required=False, widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['anggota'].queryset = Anggota.objects.all()
        self.fields['admin'].queryset = Admin.objects.all()


class PenarikanForm(forms.ModelForm):
    class Meta:
        model = Penarikan
        fields = ['anggota', 'jenis_simpanan', 'jumlah_penarikan', 'tanggal_penarikan']
        widgets = {
            'tanggal_penarikan': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        anggota = cleaned_data.get("anggota")
        jumlah_penarikan = cleaned_data.get("jumlah_penarikan")

        if anggota and jumlah_penarikan:
            # Hitung total simpanan anggota
            total_simpanan = Simpanan.objects.filter(anggota=anggota).aggregate(
                total=Sum("jumlah_menyimpan")
            )["total"] or 0

            # Hitung total penarikan sebelumnya
            total_penarikan = Penarikan.objects.filter(anggota=anggota).aggregate(
                total=Sum("jumlah_penarikan")
            )["total"] or 0

            sisa_saldo = total_simpanan - total_penarikan

            if jumlah_penarikan > sisa_saldo:
                raise forms.ValidationError(
                    f"Saldo tidak mencukupi. Sisa saldo anggota hanya Rp {sisa_saldo:,.0f}"
                )

        return cleaned_data
