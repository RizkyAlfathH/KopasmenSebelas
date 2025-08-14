from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from .models import Admin
from .forms import LoginForm

ALLOWED_ROLES = {'ketua', 'sekretaris', 'bendahara'}

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username'].strip()
            password = form.cleaned_data['password']
            try:
                admin = Admin.objects.get(username=username)
            except Admin.DoesNotExist:
                messages.error(request, "Username atau password salah.")
            else:
                if admin.role not in ALLOWED_ROLES:
                    messages.error(request, "Role tidak diperbolehkan.")
                elif admin.check_password(password):
                    request.session['admin_id'] = admin.id_admin
                    request.session['admin_username'] = admin.username
                    request.session['admin_role'] = admin.role
                    return redirect(reverse('dashboard'))
                else:
                    messages.error(request, "Username atau password salah.")
    else:
        form = LoginForm()
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    request.session.flush()
    messages.info(request, "Logout berhasil.")
    return redirect('login')

def dashboard_view(request):
    if not request.session.get('admin_id'):
        return redirect('login')

    role = request.session.get('admin_role')
    username = request.session.get('admin_username')

    if role == 'ketua':
        tpl = 'dashboard_ketua.html'
    elif role == 'sekretaris':
        tpl = 'dashboard_sekretaris.html'
    elif role == 'bendahara':
        tpl = 'dashboard_bendahara.html'

    return render(request, tpl, {'username': username, 'role': role})
