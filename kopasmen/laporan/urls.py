from django.urls import path
from . import views

urlpatterns = [
    path("", views.laporan_gabungan, name="laporan"),

]