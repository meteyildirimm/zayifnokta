"""YAML dosyasını okur, kontrol eder ve Ag nesnesine çevirir."""

import yaml

from .model import Ag, AgHatasi, Servis

AYIRAC = "<->"


def dosyadan_yukle(yol: str) -> Ag:
    try:
        with open(yol, encoding="utf-8") as f:
            return metinden_yukle(f.read())
    except FileNotFoundError:
        raise AgHatasi(f"Dosya bulunamadı: {yol}")


def metinden_yukle(metin: str) -> Ag:
    try:
        veri = yaml.safe_load(metin)
    except yaml.YAMLError as e:
        raise AgHatasi(f"YAML okunamadı (girintileri kontrol edin): {e}")
    if not isinstance(veri, dict):
        raise AgHatasi("Dosyanın en üstünde 'cihazlar', 'baglantilar' vb. başlıklar olmalı.")

    cihazlar, kapasiteler = _cihazlari_oku(veri.get("cihazlar"))
    giris = veri.get("giris_noktasi")
    if giris not in cihazlar:
        raise AgHatasi(f"'giris_noktasi' cihaz listesinde yok: {giris!r}")
    baglantilar = _baglantilari_oku(veri.get("baglantilar"), cihazlar)
    servisler = _servisleri_oku(veri.get("servisler"), cihazlar)
    return Ag(cihazlar, baglantilar, servisler, giris, kapasiteler)


def _sayi_mi(deger) -> bool:
    return isinstance(deger, (int, float)) and not isinstance(deger, bool)


def _cihazlari_oku(ham):
    if not ham:
        raise AgHatasi("'cihazlar' listesi boş veya eksik.")
    cihazlar, kapasiteler = {}, {}
    for madde in ham:
        kapasite = None
        if isinstance(madde, str):
            isim, tur = madde, "cihaz"
        elif isinstance(madde, dict) and "isim" in madde:
            isim, tur = madde["isim"], madde.get("tur", "cihaz")
            kapasite = madde.get("kapasite")
        else:
            raise AgHatasi(f"Geçersiz cihaz tanımı: {madde!r}")
        if isim in cihazlar:
            raise AgHatasi(f"Aynı isimde iki cihaz var: {isim}")
        if kapasite is not None:
            if not _sayi_mi(kapasite) or kapasite <= 0:
                raise AgHatasi(f"Cihaz '{isim}' için 'kapasite' sıfırdan büyük bir sayı olmalı.")
            kapasiteler[isim] = kapasite
        cihazlar[isim] = tur
    return cihazlar, kapasiteler


def _baglantilari_oku(ham, cihazlar) -> list:
    baglantilar = []
    for madde in ham or []:
        parcalar = [p.strip() for p in str(madde).split(AYIRAC)]
        if len(parcalar) != 2 or not all(parcalar):
            raise AgHatasi(f"Bağlantı 'a {AYIRAC} b' biçiminde olmalı: {madde!r}")
        a, b = parcalar
        for isim in (a, b):
            if isim not in cihazlar:
                raise AgHatasi(f"Bağlantıda tanımsız cihaz var ({isim}): {madde!r}")
        if a == b:
            raise AgHatasi(f"Bir cihaz kendine bağlanamaz: {madde!r}")
        baglantilar.append((a, b))
    return baglantilar


def _servisleri_oku(ham, cihazlar) -> dict:
    servisler = {}
    for madde in ham or []:
        if not isinstance(madde, dict) or "isim" not in madde:
            raise AgHatasi(f"Geçersiz servis tanımı: {madde!r}")
        isim = madde["isim"]
        if isim in servisler:
            raise AgHatasi(f"Aynı isimde iki servis var: {isim}")
        hostlar = madde.get("calistigi_yer")
        if isinstance(hostlar, str):
            hostlar = [hostlar]
        if not hostlar:
            raise AgHatasi(f"Servis '{isim}' için 'calistigi_yer' yazılmamış.")
        for h in hostlar:
            if h not in cihazlar:
                raise AgHatasi(f"Servis '{isim}' tanımsız bir cihazda çalışıyor: {h}")
        onem = madde.get("onem", 3)
        if not isinstance(onem, int) or isinstance(onem, bool) or not 1 <= onem <= 5:
            raise AgHatasi(f"Servis '{isim}' için 'onem' 1 ile 5 arasında bir sayı olmalı.")
        yuk = madde.get("yuk", 0)
        if not _sayi_mi(yuk) or yuk < 0:
            raise AgHatasi(f"Servis '{isim}' için 'yuk' sıfır ya da pozitif bir sayı olmalı.")
        servisler[isim] = Servis(
            isim, list(hostlar), list(madde.get("ihtiyac_duydugu") or []), onem, float(yuk)
        )

    for s in servisler.values():
        for b in s.bagimliliklar:
            if b not in servisler:
                raise AgHatasi(f"Servis '{s.isim}' tanımsız bir servise bağımlı: {b}")
    return servisler
