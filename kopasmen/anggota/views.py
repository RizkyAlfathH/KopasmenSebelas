from django.shortcuts import render, redirect, get_object_or_404
from .models import Anggota
from admin_koperasi.models import Admin
from .forms import AdminForm, AnggotaForm
from django.contrib.auth.models import User

def kelola_akun_view(request):
    anggotas = Anggota.objects.all() 
    return render(request, 'kelola_akun.html', {'anggotas': anggotas})

def tambah_admin(request):
    if request.method == 'POST':
        form = AdminForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('kelola_akun') 
    else:
        form = AdminForm()
    return render(request, 'form_admin.html', {'form': form})

def tambah_anggota(request):
    if request.method == 'POST':
        form = AnggotaForm(request.POST)
        if form.is_valid():
            form.save() 
            return redirect('kelola_akun') 
        form = AnggotaForm()
    
    return render(request, 'form_admin.html', {'form': form, 'judul': 'Tambah Anggota'})

def anggota_detail(request, id_anggota):
    try:
        anggota = Anggota.objects.get(id_anggota=id_anggota)
        return render(request, 'detail.html', {'anggota': anggota})
    except Anggota.DoesNotExist:
        return render(request, 'detail.html', {'error': 'Anggota not found'})
    
def edit_anggota(request, id_anggota):
    anggota = get_object_or_404(Anggota, id_anggota=id_anggota)
    form = AnggotaForm(request.POST or None, instance=anggota)
    if form.is_valid():
        form.save()
        return redirect('kelola_akun')
    return render(request, 'form_anggota.html', {'form': form, 'judul': 'Edit Anggota'})


def hapus_anggota(request, id_anggota):
    anggota = get_object_or_404(Anggota, id_anggota=id_anggota)
    anggota.delete()
    return redirect('kelola_akun')


def detail_anggota(request, id_anggota):
    anggota = get_object_or_404(Anggota, id_anggota=id_anggota)
    return render(request, 'detail.html', {'anggota': anggota})