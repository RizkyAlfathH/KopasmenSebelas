from django import forms
from django.contrib.auth.hashers import make_password
from django.utils.timezone import now
from admin_koperasi.models import Admin
from .models import Anggota


class AdminForm(forms.ModelForm):
    class Meta:
        model = Admin
        fields = ['username', 'password_hash', 'role']
        labels = {
            'password_hash': 'Password',
        }
        widgets = {
            'password_hash': forms.PasswordInput(),
        }

    def save(self, commit=True):
        admin = super().save(commit=False)
        if (
            self.cleaned_data.get('password_hash')
            and not admin.password_hash.startswith('pbkdf2_sha256$')
        ):
            admin.password_hash = make_password(self.cleaned_data['password_hash'])
        if commit:
            admin.save()
        return admin


class AnggotaForm(forms.ModelForm):
    tanggal_daftar = forms.DateField(
        widget=forms.DateInput(
            attrs={
                'type': 'date',
                'readonly': 'readonly',
            }
        ),
        initial=lambda: now().date(),  # ✅ pakai lambda
        required=False,
    )

    tanggal_nonaktif = forms.DateField(
        widget=forms.DateInput(
            attrs={
                'type': 'date',
            }
        ),
        initial=lambda: now().date(),  # ✅ pakai lambda juga
        required=False,
    )

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'placeholder': 'contoh@email.com'}),
    )

    class Meta:
        model = Anggota
        fields = '__all__'
        labels = {
            'nomor_anggota': 'No. Anggota',
            'nama': 'Nama',
            'umur': 'Umur',
            'nip': 'Nomor Induk Pegawai (NIP)',
            'alamat': 'Alamat',
            'no_telp': 'No. Telepon',
            'email': 'Email',
            'jenis_kelamin': 'Jenis Kelamin',
            'pekerjaan': 'Pekerjaan',
            'tanggal_daftar': 'Tanggal Daftar',
            'status': 'Status',
            'alasan_nonaktif': 'Alasan Nonaktif',
            'tanggal_nonaktif': 'Tanggal Nonaktif',
            'password_hash': 'Password',
        }
        widgets = {
            'password_hash': forms.PasswordInput(render_value=True),
        }

    def clean_email(self):
        email = self.cleaned_data['email']
        qs = Anggota.objects.filter(email=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Email ini sudah terdaftar.")
        return email

    def clean_nomor_anggota(self):
        nomor = self.cleaned_data['nomor_anggota']
        qs = Anggota.objects.filter(nomor_anggota=nomor)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Nomor anggota ini sudah terdaftar.")
        return nomor
    
    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        if status == 'Nonaktif':
            if not cleaned_data.get('alasan_nonaktif'):
                self.add_error('alasan_nonaktif', 'Wajib diisi jika status nonaktif.')
            if not cleaned_data.get('tanggal_nonaktif'):
                self.add_error('tanggal_nonaktif', 'Wajib diisi jika status nonaktif.')
        return cleaned_data



    def save(self, commit=True):
        anggota = super().save(commit=False)
        anggota.tanggal_daftar = now().date()

        if (
            self.cleaned_data.get('password_hash')
            and not anggota.password_hash.startswith('pbkdf2_sha256$')
        ):
            anggota.password_hash = make_password(self.cleaned_data['password_hash'])

        if commit:
            anggota.save()
        return anggota