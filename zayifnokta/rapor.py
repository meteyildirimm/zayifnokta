"""Sonuçları metin, JSON, Markdown ya da Graphviz .dot olarak yazar."""

import json
from dataclasses import asdict

from . import __version__
from .model import Ag, Sonuc

ILK_N_CIFT = 10  # metin/markdown raporunda gösterilecek en fazla çift arıza sayısı


def _liste(ogeler) -> str:
    return ", ".join(ogeler) if ogeler else "-"


def _yuk_metni(asiri: dict) -> str:
    return ", ".join(
        f"{h} (yük {v['yuk']:g} / kapasite {v['kapasite']:g})" for h, v in sorted(asiri.items())
    )


def _tablo(basliklar, satirlar) -> list:
    n = len(basliklar)
    gen = [max(len(str(r[i])) for r in [basliklar] + satirlar) + 2 for i in range(n)]

    def satir(r):
        return "".join(str(r[i]).ljust(gen[i]) for i in range(n - 1)) + str(r[-1])

    return [satir(basliklar)] + [satir(r) for r in satirlar]


def _md_tablo(basliklar, satirlar) -> list:
    cikti = ["| " + " | ".join(basliklar) + " |", "|" + "|".join(["---"] * len(basliklar)) + "|"]
    for r in satirlar:
        cikti.append("| " + " | ".join(str(x).replace("|", "\\|") for x in r) + " |")
    return cikti


def _gruplar(sonuclar):
    spoflar = [s for s in sonuclar if s.spof]
    kapasite = [s for s in sonuclar if s.kapasite_riski and not s.spof]
    return spoflar, kapasite


def senaryo_raporu(s: Sonuc) -> str:
    baslik = {
        "cihaz": f"{s.bilesen} cihazı bozulursa:",
        "kablo": f"{s.bilesen} kablosu bozulursa:",
        "cift": f"{s.bilesen} aynı anda bozulursa:",
    }[s.tur]
    satirlar = [
        baslik,
        f"  Kopan cihazlar      : {_liste(s.kopan_cihazlar)}",
        f"  Çalışmayan servisler: {_liste(s.calismayan_servisler)}",
    ]
    if s.yeni_kayip:
        satirlar.append(f"  Yalnızca birlikte   : {_liste(s.yeni_kayip)} (tek tek bozulunca kaybolmaz)")
    if s.asiri_yuklu:
        satirlar.append(f"  Aşırı yüklenen      : {_yuk_metni(s.asiri_yuklu)}")
        satirlar.append(f"  Yavaşlayan servisler: {_liste(s.yavaslayan_servisler)}")
    satirlar.append(
        f"  Risk                : {s.risk_seviyesi} (%{round(s.risk_orani * 100)} önem kaybı)"
        + ("  <- SPOF" if s.spof else "")
    )
    if s.spof:
        satirlar.append("  Öneri               : Bu bileşen için yedek (ikinci bir yol/cihaz) düşünün.")
    elif s.asiri_yuklu:
        satirlar.append("  Öneri               : Yedek cihazın kapasitesini artırın ya da yükü dağıtın.")
    return "\n".join(satirlar)


def ozet_rapor(ag: Ag, temel: Sonuc, sonuclar: list, ciftler=None) -> str:
    c = ["=" * 64, "ZAYIF NOKTA ANALİZİ", "=" * 64]
    c.append(
        f"Cihaz: {len(ag.cihazlar)}   Bağlantı: {len(ag.baglantilar)}   "
        f"Servis: {len(ag.servisler)}   Giriş noktası: {ag.giris_noktasi}"
    )

    if temel.calismayan_servisler or temel.kopan_cihazlar:
        c += ["", "UYARI: Hiçbir arıza yokken bile bazı şeyler çalışmıyor görünüyor."]
        c.append(f"  Ulaşılamayan cihazlar: {_liste(temel.kopan_cihazlar)}")
        c.append(f"  Çalışmayan servisler : {_liste(temel.calismayan_servisler)}")
        c.append("  YAML dosyasında bağlantı eksik olabilir; sonuçlar yanıltıcı olabilir.")
    if temel.asiri_yuklu:
        c += ["", "UYARI: Arıza yokken bile bazı cihazlar kapasitesini aşıyor:"]
        c.append(f"  {_yuk_metni(temel.asiri_yuklu)}")

    spoflar, kapasite = _gruplar(sonuclar)
    c += ["", "TEK HATA NOKTALARI (SPOF)", "-" * 64]
    if not spoflar:
        c.append("Tek başına bozulunca bir servisi durduran bileşen bulunamadı.")
    else:
        c += _tablo(
            ["Bileşen", "Tür", "Risk", "Kaybedilen servisler"],
            [[s.bilesen, s.tur, s.risk_seviyesi, _liste(s.calismayan_servisler)] for s in spoflar],
        )

    if kapasite:
        c += ["", "KAPASİTE RİSKLERİ (servis kaybı yok ama aşırı yük var)", "-" * 64]
        c += _tablo(
            ["Bileşen", "Tür", "Aşırı yüklenen cihazlar"],
            [[s.bilesen, s.tur, _yuk_metni(s.asiri_yuklu)] for s in kapasite],
        )

    if ciftler is not None:
        c += ["", "ÇİFT ARIZA: GİZLİ RİSKLER (tek tek zararsız, birlikte zararlı)", "-" * 64]
        if not ciftler:
            c.append("Böyle bir çift bulunamadı.")
        else:
            c += _tablo(
                ["Aynı anda bozulanlar", "Risk", "Yalnızca birlikte kaybedilen servisler"],
                [[s.bilesen, s.risk_seviyesi, _liste(s.yeni_kayip)] for s in ciftler[:ILK_N_CIFT]],
            )
            if len(ciftler) > ILK_N_CIFT:
                c.append(f"... ve {len(ciftler) - ILK_N_CIFT} çift daha (tamamı için --format json kullanın).")

    saglam = len(sonuclar) - len(spoflar)
    c += ["", f"Toplam {len(sonuclar)} bileşen denendi: {len(spoflar)} SPOF, {saglam} bileşen dayanıklı."]

    ayrinti = spoflar + kapasite
    if ayrinti:
        c += ["", "AYRINTILAR", "-" * 64]
        for s in ayrinti:
            c += [senaryo_raporu(s), ""]
    return "\n".join(c).rstrip() + "\n"


def markdown_rapor(ag: Ag, temel: Sonuc, sonuclar: list, ciftler=None) -> str:
    spoflar, kapasite = _gruplar(sonuclar)
    c = ["# Zayıf Nokta Analizi", ""]
    c.append(
        f"- Cihaz: **{len(ag.cihazlar)}**, bağlantı: **{len(ag.baglantilar)}**, "
        f"servis: **{len(ag.servisler)}**"
    )
    c.append(f"- Giriş noktası: `{ag.giris_noktasi}`")
    c.append(f"- Denenen bileşen: **{len(sonuclar)}** ({len(spoflar)} SPOF, {len(sonuclar) - len(spoflar)} dayanıklı)")

    if temel.calismayan_servisler or temel.kopan_cihazlar:
        c += ["", "> **Uyarı:** Arıza yokken bile bazı cihaz/servisler çalışmıyor görünüyor; "
              "YAML'daki bağlantıları kontrol edin."]
    if temel.asiri_yuklu:
        c += ["", f"> **Uyarı:** Arıza yokken bile kapasite aşımı var: {_yuk_metni(temel.asiri_yuklu)}"]

    c += ["", "## Tek hata noktaları (SPOF)", ""]
    if spoflar:
        c += _md_tablo(
            ["Bileşen", "Tür", "Risk", "Kaybedilen servisler"],
            [[f"`{s.bilesen}`", s.tur, s.risk_seviyesi, _liste(s.calismayan_servisler)] for s in spoflar],
        )
    else:
        c.append("Tek başına bozulunca bir servisi durduran bileşen bulunamadı.")

    if kapasite:
        c += ["", "## Kapasite riskleri", ""]
        c += _md_tablo(
            ["Bileşen", "Tür", "Aşırı yüklenen cihazlar", "Yavaşlayan servisler"],
            [[f"`{s.bilesen}`", s.tur, _yuk_metni(s.asiri_yuklu), _liste(s.yavaslayan_servisler)]
             for s in kapasite],
        )

    if ciftler is not None:
        c += ["", "## Çift arıza: gizli riskler", ""]
        if ciftler:
            c += _md_tablo(
                ["Aynı anda bozulanlar", "Risk", "Yalnızca birlikte kaybedilen servisler"],
                [[f"`{s.bilesen}`", s.risk_seviyesi, _liste(s.yeni_kayip)] for s in ciftler[:ILK_N_CIFT]],
            )
            if len(ciftler) > ILK_N_CIFT:
                c += ["", f"_... ve {len(ciftler) - ILK_N_CIFT} çift daha (tamamı için JSON çıktısı kullanın)._"]
        else:
            c.append("Tek tek zararsız olup birlikte servis kaybettiren çift bulunamadı.")
    return "\n".join(c) + "\n"


def _sozluk(s: Sonuc) -> dict:
    d = asdict(s)
    d["spof"] = s.spof
    d["kapasite_riski"] = s.kapasite_riski
    return d


def json_rapor(ag: Ag, temel: Sonuc, sonuclar: list, ciftler=None) -> str:
    veri = {
        "arac": "zayifnokta",
        "surum": __version__,
        "ozet": {
            "cihaz": len(ag.cihazlar),
            "baglanti": len(ag.baglantilar),
            "servis": len(ag.servisler),
            "giris_noktasi": ag.giris_noktasi,
        },
        "temel_durum": _sozluk(temel),
        "tekli_arizalar": [_sozluk(s) for s in sonuclar],
    }
    if ciftler is not None:
        veri["cift_arizalar"] = [_sozluk(s) for s in ciftler]
    return json.dumps(veri, ensure_ascii=False, indent=2) + "\n"


def dot_uret(ag: Ag, sonuclar: list) -> str:
    """Graphviz .dot metni üretir. SPOF cihazlar kırmızı, kapasite riski olanlar turuncu boyanır."""
    spof = {s.bilesen for s in sonuclar if s.spof and s.tur == "cihaz"}
    kapasite = {s.bilesen for s in sonuclar if s.kapasite_riski and not s.spof and s.tur == "cihaz"}
    satirlar = ["graph ag {", '  node [shape=box, style=filled, fillcolor="#e8f0fe"];']
    for isim, tur in ag.cihazlar.items():
        ozellik = [f'label="{isim}\\n({tur})"']
        if isim in spof:
            ozellik.append('fillcolor="#f8b4b4"')
        elif isim in kapasite:
            ozellik.append('fillcolor="#fde3b0"')
        if isim == ag.giris_noktasi:
            ozellik.append("peripheries=2")
        satirlar.append(f'  "{isim}" [{", ".join(ozellik)}];')
    for a, b in ag.baglantilar:
        satirlar.append(f'  "{a}" -- "{b}";')
    satirlar.append("}")
    return "\n".join(satirlar) + "\n"
