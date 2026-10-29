"""Veri modelleri: ağı ve analiz sonuçlarını tutan basit sınıflar."""

from dataclasses import dataclass, field


class AgHatasi(Exception):
    """YAML dosyasında bir hata olduğunda fırlatılır (kullanıcıya gösterilir)."""


@dataclass
class Servis:
    isim: str
    hostlar: list          # servisin çalıştığı cihazlar (birden fazlaysa yedekli demektir)
    bagimliliklar: list = field(default_factory=list)  # ihtiyaç duyduğu diğer servisler
    onem: int = 3          # 1 (önemsiz) ... 5 (hayati)
    yuk: float = 0.0       # servisin toplam yükü; çalışan hostlara eşit bölüşülür


@dataclass
class Ag:
    cihazlar: dict         # isim -> tür (örn. "switch", "sunucu")
    baglantilar: list      # [(cihaz_a, cihaz_b), ...]
    servisler: dict        # isim -> Servis
    giris_noktasi: str     # kullanıcıların / internetin ağa girdiği cihaz
    kapasiteler: dict = field(default_factory=dict)  # isim -> kapasite (yazılmayan = sınırsız)


@dataclass
class Sonuc:
    """Tek bir "şu bozulursa ne olur?" senaryosunun sonucu."""

    tur: str                   # "cihaz", "kablo" veya "cift"
    bilesen: str               # bozulan şey(ler)in adı
    kopan_cihazlar: list       # ağdan kopan (ulaşılamayan) cihazlar
    calismayan_servisler: list
    kayip_onem: int            # tamamen kaybedilen servislerin önem toplamı
    risk_orani: float          # 0.0 ... 1.0 (yavaşlayan servisler yarım sayılır)
    risk_seviyesi: str         # YOK / DÜŞÜK / ORTA / YÜKSEK / KRİTİK
    yavaslayan_servisler: list = field(default_factory=list)  # çalışıyor ama aşırı yüklü cihazda
    asiri_yuklu: dict = field(default_factory=dict)  # cihaz -> {"yuk": ..., "kapasite": ...}
    yeni_kayip: list = field(default_factory=list)   # (çift arıza) tek tek denenince kaybolmayanlar

    @property
    def spof(self) -> bool:
        """Bu bileşen bozulunca en az bir servis çalışmaz oluyorsa SPOF'tur."""
        return len(self.calismayan_servisler) > 0

    @property
    def kapasite_riski(self) -> bool:
        """Servis kaybı olmasa bile bir cihaz kapasitesini aşıyorsa True."""
        return len(self.asiri_yuklu) > 0
