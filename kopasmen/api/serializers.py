from rest_framework import serializers
from anggota.models import Anggota
from simpanan.models import JenisSimpanan, Simpanan, Penarikan
from pinjaman.models import Pinjaman, Angsuran, JenisPinjaman, KategoriJasa
from pinjaman.models import Pinjaman, Angsuran, JenisPinjaman, KategoriJasa


class LoginSerializer(serializers.Serializer):
    nomor_anggota = serializers.CharField()
    password = serializers.CharField(write_only=True)


class ResetPasswordSerializer(serializers.Serializer):
    nomor_anggota = serializers.CharField()
    password = serializers.CharField(write_only=True)


class AnggotaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Anggota
        fields = ["nomor_anggota", "nama", "nip", "email", "status"]

class ProfilAnggotaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Anggota
        fields = '__all__' 
        
class JenisSimpananSerializer(serializers.ModelSerializer):
    class Meta:
        model = JenisSimpanan
        fields = ["id_jenis_simpanan", "nama_jenis"]


class SimpananSerializer(serializers.ModelSerializer):
    anggota = serializers.StringRelatedField()
    admin = serializers.StringRelatedField()
    jenis_simpanan = JenisSimpananSerializer()
    nominal = serializers.DecimalField(
        source="jumlah_menyimpan", max_digits=18, decimal_places=2
    )  

    class Meta:
        model = Simpanan
        fields = [
            "id_simpanan",
            "anggota",
            "admin",
            "jenis_simpanan",
            "tanggal_menyimpan",
            "tanggal_menarik",
            "nominal",
        ]


class PenarikanSerializer(serializers.ModelSerializer):
    anggota = serializers.StringRelatedField()
    admin = serializers.StringRelatedField()
    jenis_simpanan = JenisSimpananSerializer()
    nominal = serializers.DecimalField(
        source="jumlah_penarikan", max_digits=18, decimal_places=2
    )

    class Meta:
        model = Penarikan
        fields = [
            "id_penarikan",
            "anggota",
            "admin",
            "jenis_simpanan",
            "tanggal_penarikan",
            "nominal",
        ]


class JenisPinjamanSerializer(serializers.ModelSerializer):
    class Meta:
        model = JenisPinjaman
        fields = ["id_jenis_pinjaman", "nama_jenis"]


class KategoriJasaSerializer(serializers.ModelSerializer):
    class Meta:
        model = KategoriJasa
        fields = ["id_kategori_jasa", "kategori_jasa"]


class PinjamanSerializer(serializers.ModelSerializer):
    anggota = serializers.StringRelatedField(source="nomor_anggota")
    jenis_pinjaman = JenisPinjamanSerializer(source="id_jenis_pinjaman")
    kategori_pinjaman = KategoriJasaSerializer(source="id_kategori_jasa")
    cicilan_terbayar = serializers.SerializerMethodField()
    sisa_pinjaman = serializers.SerializerMethodField()

    class Meta:
        model = Pinjaman
        fields = [
            "id_pinjaman",
            "anggota",
            "jumlah_pinjaman",
            "angsuran_per_bulan",
            "jasa_persen",
            "jasa_rupiah",         
            "status",
            "tanggal_meminjam",
            "jatuh_tempo",     
            "jenis_pinjaman",
            "kategori_pinjaman",
            "cicilan_terbayar",
            "sisa_pinjaman",
        ]

    def get_cicilan_terbayar(self, obj):
        return Angsuran.objects.filter(id_pinjaman=obj).count()

    def get_sisa_pinjaman(self, obj):
        angsuran_pokok = obj.angsuran_per_bulan or 0
        jumlah_cicilan_terbayar = Angsuran.objects.filter(id_pinjaman=obj).count()
        total_pokok_bayar = jumlah_cicilan_terbayar * angsuran_pokok
        return obj.jumlah_pinjaman - total_pokok_bayar


class AngsuranSerializer(serializers.ModelSerializer):
    admin = serializers.StringRelatedField()
    nominal = serializers.DecimalField(
        source="jumlah_bayar", max_digits=18, decimal_places=2
    )

    class Meta:
        model = Angsuran
        fields = ["id_pembayaran", "id_pinjaman", "admin", "tanggal_bayar", "nominal"]