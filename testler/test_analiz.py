"""Testler. Çalıştırmak için:  python -m unittest discover -s testler -v"""

import contextlib
import io
import json
import os
import tempfile
import unittest

from zayifnokta.analiz import (
    cift_arizalar,
    cihaz_bozulursa,
    kablo_bozulursa,
    temel_durum,
    tum_analiz,
)
from zayifnokta.cli import main
from zayifnokta.model import AgHatasi
from zayifnokta.rapor import json_rapor, markdown_rapor, ozet_rapor
from zayifnokta.yukle import dosyadan_yukle, metinden_yukle

ORNEK = os.path.join(os.path.dirname(__file__), "..", "ornekler", "ornek_ag.yaml")

ZINCIR = """
giris_noktasi: router
cihazlar: [router, switch, sunucu]
baglantilar:
  - router <-> switch
  - switch <-> sunucu
servisler:
  - {isim: uygulama, calistigi_yer: sunucu, onem: 4}
"""

# İki ayrı yoldan bağlı yedekli sunucu: tek arızada sağlam, çift arızada çöker.
YEDEKLI = """
giris_noktasi: r
cihazlar: [r, s1, s2, a, b]
baglantilar:
  - r <-> s1
  - r <-> s2
  - s1 <-> a
  - s2 <-> b
servisler:
  - {isim: uyg, calistigi_yer: [a, b]}
"""


class AnalizTestleri(unittest.TestCase):
    def test_switch_bozulursa_sunucu_kopar(self):
        s = cihaz_bozulursa(metinden_yukle(ZINCIR), "switch")
        self.assertEqual(s.kopan_cihazlar, ["sunucu"])
        self.assertEqual(s.calismayan_servisler, ["uygulama"])
        self.assertTrue(s.spof)
        self.assertEqual(s.risk_seviyesi, "KRİTİK")

    def test_arizasiz_durumda_her_sey_calisir(self):
        s = temel_durum(metinden_yukle(ZINCIR))
        self.assertEqual(s.calismayan_servisler, [])
        self.assertEqual(s.kopan_cihazlar, [])
        self.assertEqual(s.risk_seviyesi, "YOK")

    def test_giris_noktasi_bozulursa_her_sey_gider(self):
        s = cihaz_bozulursa(metinden_yukle(ZINCIR), "router")
        self.assertEqual(s.kopan_cihazlar, ["sunucu", "switch"])
        self.assertEqual(s.calismayan_servisler, ["uygulama"])

    def test_kablo_bozulmasi(self):
        s = kablo_bozulursa(metinden_yukle(ZINCIR), 1)  # switch <-> sunucu
        self.assertEqual(s.kopan_cihazlar, ["sunucu"])
        self.assertTrue(s.spof)

    def test_yedekli_kablo_spof_degildir(self):
        ag = metinden_yukle(ZINCIR.replace(
            "  - switch <-> sunucu\n", "  - switch <-> sunucu\n  - switch <-> sunucu\n"))
        self.assertFalse(kablo_bozulursa(ag, 1).spof)

    def test_yedekli_servis_ayakta_kalir(self):
        s = cihaz_bozulursa(dosyadan_yukle(ORNEK), "sunucu-web1")
        self.assertNotIn("web-sitesi", s.calismayan_servisler)
        self.assertFalse(s.spof)

    def test_bagimlilik_zinciri(self):
        s = cihaz_bozulursa(dosyadan_yukle(ORNEK), "sunucu-db")
        self.assertEqual(s.calismayan_servisler, ["veritabani", "web-sitesi"])

    def test_bagimli_servis_de_duser(self):
        s = cihaz_bozulursa(dosyadan_yukle(ORNEK), "sunucu-dosya")
        self.assertEqual(s.calismayan_servisler, ["dosya-paylasimi", "yedekleme"])

    def test_ornek_ag_saglam_ve_sirali(self):
        ag = dosyadan_yukle(ORNEK)
        t = temel_durum(ag)
        self.assertEqual(t.calismayan_servisler, [])
        self.assertEqual(t.asiri_yuklu, {})
        sonuclar = tum_analiz(ag)
        kayiplar = [s.kayip_onem for s in sonuclar]
        self.assertEqual(kayiplar, sorted(kayiplar, reverse=True))
        spoflar = {s.bilesen for s in sonuclar if s.spof and s.tur == "cihaz"}
        self.assertIn("core-switch", spoflar)
        self.assertIn("firewall-1", spoflar)
        self.assertNotIn("sunucu-web1", spoflar)


class KapasiteTestleri(unittest.TestCase):
    def test_yedek_yuku_kaldiramazsa_asiri_yuk(self):
        s = cihaz_bozulursa(dosyadan_yukle(ORNEK), "sunucu-web1")
        self.assertFalse(s.spof)
        self.assertTrue(s.kapasite_riski)
        self.assertEqual(s.asiri_yuklu["sunucu-web2"], {"yuk": 12.0, "kapasite": 10})
        self.assertEqual(s.yavaslayan_servisler, ["web-sitesi"])
        self.assertGreater(s.risk_orani, 0)

    def test_kopan_yedek_de_kapasite_riski_dogurur(self):
        s = cihaz_bozulursa(dosyadan_yukle(ORNEK), "kat1-switch")  # web2 kopar
        self.assertFalse(s.spof)
        self.assertIn("sunucu-web1", s.asiri_yuklu)

    def test_kapasite_yeterliyse_risk_yok(self):
        ag = dosyadan_yukle(ORNEK)
        ag.kapasiteler["sunucu-web1"] = 20
        ag.kapasiteler["sunucu-web2"] = 20
        self.assertFalse(cihaz_bozulursa(ag, "sunucu-web1").kapasite_riski)

    def test_kapasite_yazilmayan_cihaz_sinirsizdir(self):
        ag = metinden_yukle(YEDEKLI)
        ag.servisler["uyg"].yuk = 999
        self.assertEqual(temel_durum(ag).asiri_yuklu, {})


class CiftArizaTestleri(unittest.TestCase):
    def test_tekli_arizalar_zararsiz_cift_zararli(self):
        ag = metinden_yukle(YEDEKLI)
        for c in ("s1", "s2", "a", "b"):
            self.assertFalse(cihaz_bozulursa(ag, c).spof)
        ciftler = cift_arizalar(ag)
        adlar = {s.bilesen for s in ciftler}
        self.assertIn("s1 + s2", adlar)
        self.assertIn("a + b", adlar)
        for s in ciftler:
            self.assertEqual(s.yeni_kayip, ["uyg"])
            self.assertEqual(s.tur, "cift")

    def test_cihaz_ve_kendi_kablosu_denenmez(self):
        ag = metinden_yukle(YEDEKLI)
        adlar = {s.bilesen for s in cift_arizalar(ag)}
        self.assertNotIn("s1 + r <-> s1", adlar)

    def test_zaten_spof_olan_gizli_risk_sayilmaz(self):
        ag = metinden_yukle(ZINCIR)
        self.assertEqual(cift_arizalar(ag), [])


class RaporTestleri(unittest.TestCase):
    def setUp(self):
        self.ag = dosyadan_yukle(ORNEK)
        self.t = temel_durum(self.ag)
        self.s = tum_analiz(self.ag)
        self.c = cift_arizalar(self.ag)

    def test_json_gecerli_ve_tam(self):
        veri = json.loads(json_rapor(self.ag, self.t, self.s, self.c))
        self.assertEqual(veri["arac"], "zayifnokta")
        self.assertEqual(veri["ozet"]["cihaz"], 8)
        self.assertEqual(len(veri["tekli_arizalar"]), len(self.s))
        self.assertIn("cift_arizalar", veri)
        self.assertTrue(any(x["spof"] for x in veri["tekli_arizalar"]))

    def test_json_cift_istenmezse_yok(self):
        veri = json.loads(json_rapor(self.ag, self.t, self.s))
        self.assertNotIn("cift_arizalar", veri)

    def test_markdown_basliklari(self):
        md = markdown_rapor(self.ag, self.t, self.s, self.c)
        self.assertIn("# Zayıf Nokta Analizi", md)
        self.assertIn("## Tek hata noktaları (SPOF)", md)
        self.assertIn("## Kapasite riskleri", md)
        self.assertIn("## Çift arıza", md)

    def test_metin_raporu(self):
        metin = ozet_rapor(self.ag, self.t, self.s, self.c)
        self.assertIn("ZAYIF NOKTA ANALİZİ", metin)
        self.assertIn("KAPASİTE RİSKLERİ", metin)
        self.assertIn("ÇİFT ARIZA", metin)


class CliTestleri(unittest.TestCase):
    def calistir(self, *argumanlar):
        cikti = io.StringIO()
        with contextlib.redirect_stdout(cikti), contextlib.redirect_stderr(io.StringIO()):
            kod = main(list(argumanlar))
        return kod, cikti.getvalue()

    def test_varsayilan_metin(self):
        kod, cikti = self.calistir(ORNEK)
        self.assertEqual(kod, 0)
        self.assertIn("TEK HATA NOKTALARI", cikti)

    def test_json_stdout_ayristirilabilir(self):
        kod, cikti = self.calistir(ORNEK, "--format", "json", "--cift")
        self.assertEqual(kod, 0)
        self.assertIn("cift_arizalar", json.loads(cikti))

    def test_dosyaya_yazma(self):
        with tempfile.TemporaryDirectory() as d:
            yol = os.path.join(d, "rapor.md")
            kod, cikti = self.calistir(ORNEK, "--format", "markdown", "--cikti", yol)
            self.assertEqual(kod, 0)
            self.assertEqual(cikti, "")
            with open(yol, encoding="utf-8") as f:
                self.assertIn("# Zayıf Nokta Analizi", f.read())

    def test_tek_cihaz(self):
        kod, cikti = self.calistir(ORNEK, "--cihaz", "sunucu-web1")
        self.assertEqual(kod, 0)
        self.assertIn("Aşırı yüklenen", cikti)

    def test_hatali_cihaz_ve_dosya(self):
        self.assertEqual(self.calistir(ORNEK, "--cihaz", "yok")[0], 1)
        self.assertEqual(self.calistir("yok.yaml")[0], 1)


class YuklemeTestleri(unittest.TestCase):
    def test_tanimsiz_cihaz_baglantisi(self):
        with self.assertRaises(AgHatasi):
            metinden_yukle("giris_noktasi: a\ncihazlar: [a]\nbaglantilar: ['a <-> b']")

    def test_tanimsiz_bagimlilik(self):
        with self.assertRaises(AgHatasi):
            metinden_yukle(ZINCIR.replace("onem: 4", "onem: 4, ihtiyac_duydugu: [yok-boyle]"))

    def test_gecersiz_onem(self):
        with self.assertRaises(AgHatasi):
            metinden_yukle(ZINCIR.replace("onem: 4", "onem: 9"))

    def test_gecersiz_giris_noktasi(self):
        with self.assertRaises(AgHatasi):
            metinden_yukle(ZINCIR.replace("giris_noktasi: router", "giris_noktasi: yok"))

    def test_ayni_isimli_cihaz(self):
        with self.assertRaises(AgHatasi):
            metinden_yukle("giris_noktasi: a\ncihazlar: [a, a]")

    def test_olmayan_dosya(self):
        with self.assertRaises(AgHatasi):
            dosyadan_yukle("yok.yaml")

    def test_gecersiz_kapasite_ve_yuk(self):
        with self.assertRaises(AgHatasi):
            metinden_yukle("giris_noktasi: a\ncihazlar: [{isim: a, kapasite: -5}]")
        with self.assertRaises(AgHatasi):
            metinden_yukle("giris_noktasi: a\ncihazlar: [{isim: a, kapasite: abc}]")
        with self.assertRaises(AgHatasi):
            metinden_yukle(ZINCIR.replace("onem: 4", "onem: 4, yuk: -1"))


if __name__ == "__main__":
    unittest.main()
