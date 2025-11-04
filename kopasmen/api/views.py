from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import (
    LoginSerializer, AnggotaSerializer, ResetPasswordSerializer,
    SimpananSerializer, PenarikanSerializer,
    PinjamanSerializer, AngsuranSerializer, ProfilAnggotaSerializer
)
from anggota.models import Anggota
from simpanan.models import Simpanan, Penarikan
from pinjaman.models import Pinjaman, Angsuran
from django.db.models import Q


# ==========================
# Autentikasi & Anggota
# ==========================
class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        nomor_anggota = serializer.validated_data['nomor_anggota']
        password = serializer.validated_data['password']

        try:
            anggota = Anggota.objects.get(nomor_anggota=nomor_anggota, status="aktif")
        except Anggota.DoesNotExist:
            return Response(
                {"error": "Nomor anggota tidak ditemukan atau akun nonaktif"},
                status=status.HTTP_404_NOT_FOUND
            )

        if anggota.check_password(password):
            data = AnggotaSerializer(anggota).data
            return Response(
                {"message": "Login berhasil", "data": data},
                status=status.HTTP_200_OK
            )
        return Response({"error": "Password salah"}, status=status.HTTP_400_BAD_REQUEST)

class CheckNomorAnggotaView(APIView):
    def post(self, request):
        nomor_anggota = request.data.get("nomor_anggota")
        if not nomor_anggota:
            return Response(
                {"error": "Nomor anggota wajib diisi"},
                status=status.HTTP_400_BAD_REQUEST
            )

        exists = Anggota.objects.filter(nomor_anggota=nomor_anggota).exists()
        return Response({"exists": exists}, status=status.HTTP_200_OK)

class ResetPasswordView(APIView):
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        nomor_anggota = serializer.validated_data["nomor_anggota"]
        new_password = serializer.validated_data["password"]

        try:
            anggota = Anggota.objects.get(nomor_anggota=nomor_anggota, status="aktif")
        except Anggota.DoesNotExist:
            return Response(
                {"error": "Nomor anggota tidak ditemukan atau akun nonaktif"},
                status=status.HTTP_404_NOT_FOUND
            )

        anggota.set_password(new_password)
        anggota.save()

        return Response({"message": "Password berhasil direset"}, status=status.HTTP_200_OK)

# ==========================
# Simpanan & Penarikan
# ==========================
class SimpananListView(APIView):
    def get(self, request, nip):
        simpanan = Simpanan.objects.filter(
            anggota__nip=nip
        ).order_by('-tanggal_menyimpan')
        serializer = SimpananSerializer(simpanan, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PenarikanListView(APIView):
    def get(self, request, nip):
        penarikan = Penarikan.objects.filter(
            anggota__nip=nip
        ).order_by('-tanggal_penarikan')
        serializer = PenarikanSerializer(penarikan, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ==========================
# Pinjaman & Angsuran
# ==========================
class PinjamanListView(APIView):
    def get(self, request, nip):
        pinjaman = Pinjaman.objects.filter(
            nomor_anggota__nip=nip
        ).order_by('-tanggal_meminjam')
        serializer = PinjamanSerializer(pinjaman, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AngsuranListView(APIView):
    def get(self, request, id_pinjaman):
        angsuran = Angsuran.objects.filter(
            id_pinjaman=id_pinjaman
        ).order_by('-tanggal_bayar')
        serializer = AngsuranSerializer(angsuran, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class ProfilAnggotaView(APIView):
    def get(self, request, nip):
        # Hilangkan spasi dan ubah ke format yang aman
        clean_nip = nip.strip().replace(" ", "")

        try:
            anggota = Anggota.objects.get(
                Q(nip=nip) | Q(nomor_anggota=nip) |
                Q(nip=clean_nip) | Q(nomor_anggota=clean_nip)
            )
        except Anggota.DoesNotExist:
            return Response(
                {"detail": "Anggota tidak ditemukan"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ProfilAnggotaSerializer(anggota)
        return Response(serializer.data, status=status.HTTP_200_OK)