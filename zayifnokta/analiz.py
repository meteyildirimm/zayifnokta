"""Asıl hesaplama burada: "X bozulursa ne olur?" sorusunu cevaplar."""

from itertools import combinations

import networkx as nx

from .model import Ag, Sonuc

# Bir "bileşen", ("cihaz", isim) ya da ("kablo", bağlantı_sırası) biçiminde bir çifttir.


def _graf_kur(ag: Ag, bozuk_cihazlar, bozuk_kablolar) -> nx.Graph:
    """Ağı graf olarak kurar; bozuk cihaz/kablolar grafa hiç eklenmez."""
    g = nx.Graph()
    g.add_nodes_from(c for c in ag.cihazlar if c not in bozuk_cihazlar)
    for i, (a, b) in enumerate(ag.baglantilar):
        if i in bozuk_kablolar or a in bozuk_cihazlar or b in bozuk_cihazlar:
            continue
        g.add_edge(a, b)
    return g


def _risk_seviyesi(oran: float, kopan: list) -> str:
    if oran == 0:
        return "DÜŞÜK" if kopan else "YOK"
    if oran < 0.25:
        return "DÜŞÜK"
    if oran < 0.5:
        return "ORTA"
    if oran < 0.75:
        return "YÜKSEK"
    return "KRİTİK"


def _hesapla(ag: Ag, g: nx.Graph, tur: str, bilesen: str, bozuk_cihazlar) -> Sonuc:
    # 1) Giriş noktasından hangi cihazlara hâlâ ulaşılabiliyor?
    if ag.giris_noktasi in g:
        ulasilabilir = set(nx.node_connected_component(g, ag.giris_noktasi))
    else:
        ulasilabilir = set()
    kopan = sorted(set(ag.cihazlar) - ulasilabilir - set(bozuk_cihazlar))

    # 2) Servis, en az bir yedeği ulaşılabilir bir cihazda çalışıyorsa ayaktadır.
    calisan = {
        s.isim
        for s in ag.servisler.values()
        if any(h in ulasilabilir for h in s.hostlar)
    }

    # 3) Bağımlı olduğu servis düştüyse o da düşer. Değişiklik kalmayana dek tekrarla.
    degisti = True
    while degisti:
        degisti = False
        for isim in list(calisan):
            if any(b not in calisan for b in ag.servisler[isim].bagimliliklar):
                calisan.discard(isim)
                degisti = True

    # 4) Kapasite: ayaktaki her servisin yükü, canlı hostları arasında eşit bölüşülür.
    canli_hostlar = {
        isim: [h for h in ag.servisler[isim].hostlar if h in ulasilabilir] for isim in calisan
    }
    yukler = {}
    for isim, hostlar in canli_hostlar.items():
        yuk = ag.servisler[isim].yuk
        if yuk and hostlar:
            for h in hostlar:
                yukler[h] = yukler.get(h, 0.0) + yuk / len(hostlar)
    asiri = {
        h: {"yuk": round(y, 2), "kapasite": ag.kapasiteler[h]}
        for h, y in sorted(yukler.items())
        if h in ag.kapasiteler and y > ag.kapasiteler[h] + 1e-9
    }
    yavas = sorted(i for i, hostlar in canli_hostlar.items() if any(h in asiri for h in hostlar))

    dusen = sorted(set(ag.servisler) - calisan)
    toplam = sum(s.onem for s in ag.servisler.values())
    kayip = sum(ag.servisler[i].onem for i in dusen)
    yavas_onem = sum(ag.servisler[i].onem for i in yavas)
    oran = (kayip + 0.5 * yavas_onem) / toplam if toplam else 0.0
    return Sonuc(
        tur, bilesen, kopan, dusen, kayip, oran, _risk_seviyesi(oran, kopan),
        yavaslayan_servisler=yavas, asiri_yuklu=asiri,
    )


def _ad(ag: Ag, bilesen) -> str:
    tur, deger = bilesen
    if tur == "cihaz":
        return deger
    a, b = ag.baglantilar[deger]
    return f"{a} <-> {b}"


def _calistir(ag: Ag, bilesenler) -> Sonuc:
    cihazlar = frozenset(d for t, d in bilesenler if t == "cihaz")
    kablolar = frozenset(d for t, d in bilesenler if t == "kablo")
    g = _graf_kur(ag, cihazlar, kablolar)
    if len(bilesenler) == 1:
        tur = bilesenler[0][0]
        ad = _ad(ag, bilesenler[0])
    else:
        tur = "cift"
        ad = " + ".join(_ad(ag, b) for b in bilesenler)
    return _hesapla(ag, g, tur, ad, cihazlar)


def temel_durum(ag: Ag) -> Sonuc:
    """Hiçbir şey bozulmamışken ağın durumu (önce bunun sağlam olması gerekir)."""
    return _hesapla(ag, _graf_kur(ag, frozenset(), frozenset()), "-", "(arıza yok)", frozenset())


def cihaz_bozulursa(ag: Ag, cihaz: str) -> Sonuc:
    return _calistir(ag, [("cihaz", cihaz)])


def kablo_bozulursa(ag: Ag, index: int) -> Sonuc:
    return _calistir(ag, [("kablo", index)])


def _tum_bilesenler(ag: Ag) -> list:
    return [("cihaz", c) for c in ag.cihazlar] + [("kablo", i) for i in range(len(ag.baglantilar))]


def tum_analiz(ag: Ag) -> list:
    """Her cihaz ve her kablo için sırayla senaryo çalıştırır, en riskliden başlayarak sıralar."""
    sonuclar = [_calistir(ag, [b]) for b in _tum_bilesenler(ag)]
    sonuclar.sort(key=lambda s: (-s.kayip_onem, -len(s.kopan_cihazlar), s.bilesen))
    return sonuclar


def cift_arizalar(ag: Ag) -> list:
    """Aynı anda iki arıza: her bileşen çiftini dener.

    Yalnızca "gizli riskleri" döndürür: tek tek bozulunca zararsız olan ama
    birlikte bozulunca yeni bir servis kaybettiren çiftler.
    """
    bilesenler = _tum_bilesenler(ag)
    tekli = {b: set(_calistir(ag, [b]).calismayan_servisler) for b in bilesenler}
    sonuclar = []
    for x, y in combinations(bilesenler, 2):
        # Bir cihazla o cihaza bağlı kablo birlikte denenmez (zaten aynı şey).
        if {x[0], y[0]} == {"cihaz", "kablo"}:
            cihaz = x[1] if x[0] == "cihaz" else y[1]
            kablo = x[1] if x[0] == "kablo" else y[1]
            if cihaz in ag.baglantilar[kablo]:
                continue
        s = _calistir(ag, [x, y])
        yeni = sorted(set(s.calismayan_servisler) - tekli[x] - tekli[y])
        if yeni:
            s.yeni_kayip = yeni
            sonuclar.append(s)
    sonuclar.sort(key=lambda s: (-s.kayip_onem, -len(s.yeni_kayip), s.bilesen))
    return sonuclar
