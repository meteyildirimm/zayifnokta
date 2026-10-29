"""Komut satırı arayüzü."""

import argparse
import sys

from . import __version__
from .analiz import cift_arizalar, cihaz_bozulursa, temel_durum, tum_analiz
from .model import AgHatasi
from .rapor import dot_uret, json_rapor, markdown_rapor, ozet_rapor, senaryo_raporu
from .yukle import dosyadan_yukle

URETICILER = {"metin": ozet_rapor, "json": json_rapor, "markdown": markdown_rapor}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="zayifnokta",
        description="Ağ ve sistem altyapınızdaki tek hata noktalarını (SPOF), "
        "kapasite risklerini ve çift arıza senaryolarını bulur.",
    )
    p.add_argument("dosya", help="Ağı anlatan YAML dosyası")
    p.add_argument("--cihaz", metavar="ISIM", help="Sadece bu cihaz bozulursa ne olur, onu göster")
    p.add_argument("--cift", action="store_true", help="Aynı anda iki arıza senaryolarını da dene")
    p.add_argument("--format", choices=list(URETICILER), default="metin", help="Rapor biçimi (varsayılan: metin)")
    p.add_argument("--cikti", metavar="DOSYA", help="Raporu ekrana değil bu dosyaya yaz")
    p.add_argument("--dot", metavar="DOSYA", help="Graphviz .dot dosyası da üret")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = p.parse_args(argv)

    try:
        ag = dosyadan_yukle(args.dosya)
        if args.cihaz:
            if args.cihaz not in ag.cihazlar:
                raise AgHatasi(f"Böyle bir cihaz yok: {args.cihaz}")
            print(senaryo_raporu(cihaz_bozulursa(ag, args.cihaz)))
            return 0

        sonuclar = tum_analiz(ag)
        ciftler = cift_arizalar(ag) if args.cift else None
        rapor = URETICILER[args.format](ag, temel_durum(ag), sonuclar, ciftler)

        if args.cikti:
            with open(args.cikti, "w", encoding="utf-8") as f:
                f.write(rapor)
            print(f"Rapor yazıldı: {args.cikti}", file=sys.stderr)
        else:
            print(rapor, end="")
        if args.dot:
            with open(args.dot, "w", encoding="utf-8") as f:
                f.write(dot_uret(ag, sonuclar))
            print(f".dot dosyası yazıldı: {args.dot}", file=sys.stderr)
    except AgHatasi as e:
        print(f"HATA: {e}", file=sys.stderr)
        return 1
    return 0
