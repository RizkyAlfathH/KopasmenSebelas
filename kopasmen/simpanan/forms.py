from django import forms
from django.db.models import Sum 
from .models import Anggota, Admin, Simpanan, Penarikan
import datetime

class SimpananForm(forms.ModelForm):
    class Meta:
        model = Simpanan
        fields = [
            'admin',
            'tanggal_menyimpan',
            'anggota',
            'jenis_simpanan',
            'jumlah_menyimpan',
            'dana_sosial'
        ]
        widgets = {
            'anggota': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'anggota-autocomplete',
                'placeholder': 'Cari anggota'
            }),
            'admin': forms.HiddenInput(),
            'tanggal_menyimpan': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control'},
                format='%Y-%m-%d'
            ),
            'jenis_simpanan': forms.Select(attrs={'class': 'form-control'}),
            'jumlah_menyimpan': forms.TextInput(attrs={'class': 'form-control'}),
            'dana_sosial': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ===============================
        # DANA SOSIAL TIDAK WAJIB DEFAULT
        # ===============================
        self.fields['dana_sosial'].required = False

        # default tanggal hari ini
        if not self.instance.pk:
            self.fields['tanggal_menyimpan'].initial = datetime.date.today()

    def clean(self):
        cleaned_data = super().clean()

        anggota = cleaned_data.get('anggota')
        jenis = cleaned_data.get('jenis_simpanan')
        tanggal = cleaned_data.get('tanggal_menyimpan')
        dana_sosial = cleaned_data.get('dana_sosial')

        if not anggota or not jenis or not tanggal:
            return cleaned_data

        # SIMPANAN WAJIB = PK 2
        if jenis.pk == 2:
            bulan = tanggal.month
            tahun = tanggal.year

            sudah_bayar = Simpanan.objects.filter(
                anggota=anggota,
                jenis_simpanan_id=2,
                tanggal_menyimpan__month=bulan,
                tanggal_menyimpan__year=tahun
            ).exists()

            if not sudah_bayar and not dana_sosial:
                raise forms.ValidationError(
                    "Dana sosial wajib diisi karena anggota belum membayar simpanan wajib bulan ini."
                )

        return cleaned_data



class EditSimpananForm(forms.Form):
    tanggal_menyimpan = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'text',
            'class': 'form-control datepicker',
            'autocomplete': 'off'
        })
    )

    simpanan_pokok = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    simpanan_wajib = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    simpanan_sukarela = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )


class PenarikanForm(forms.ModelForm):
    class Meta:
        model = Penarikan
        fields = ['tanggal_penarikan', 'jumlah_penarikan']
        widgets = {
            'tanggal_penarikan': forms.DateInput(attrs={'type': 'date'}),
            'jumlah_penarikan': forms.NumberInput(attrs={'placeholder': 'Masukkan jumlah'}),
        }

    def __init__(self, *args, **kwargs):
        self.anggota = kwargs.pop("anggota", None)
        self.jenis_simpanan = kwargs.pop("jenis_simpanan", None)
        super().__init__(*args, **kwargs)

    def clean_jumlah_penarikan(self):
        jumlah = self.cleaned_data.get("jumlah_penarikan")

        if jumlah <= 0:
            raise forms.ValidationError("Jumlah penarikan tidak boleh kurang dari 1.")

        return jumlah

    def clean(self):
        cleaned_data = super().clean()

        if not (self.anggota and self.jenis_simpanan):
            return cleaned_data

        jumlah = cleaned_data.get("jumlah_penarikan")

        simpanan = Simpanan.objects.filter(
            anggota=self.anggota,
            jenis_simpanan=self.jenis_simpanan
        ).first()

        saldo = simpanan.jumlah_menyimpan if simpanan else 0

        if jumlah and jumlah > saldo:
            raise forms.ValidationError(
                f"Saldo tidak cukup. Saldo Simpanan hanya Rp {saldo:,.0f}."
            )

        return cleaned_data
