# zayifnokta (Zayıf Nokta)

> *English summary:* an offline, dependency-light CLI that reads a YAML description of your network
> (devices, cables) and services (replicas, dependencies, load) and tells you which single component
> or **pair of components** would take services down, and where a failure would overload the
> surviving replicas. Reports in text, JSON and Markdown. Documentation is in Turkish.

Ağ ve sistem altyapınızı basit bir YAML dosyasıyla tanımlayın; araç şu soruları otomatik cevaplasın:

1. **Tek bir cihaz ya da kablo bozulursa hangi servisler çalışmaz olur?** (SPOF)
2. **Yedek sunucu, düşen sunucunun yükünü kaldırabilir mi?** (kapasite kontrolü)
3. **Tek tek zararsız görünen iki arıza birlikte olursa ne olur?** (çift arıza, "gizli riskler")

Web arayüzü yoktur; terminalden çalışır. Çıktı **metin**, **JSON** ya da **Markdown** olabilir.

## Kurulum

Python 3.9+ gerekir.

```bash
pip install -r requirements.txt
# ya da komut olarak kurmak için:
pip install .          # sonra:  zayifnokta ornekler/ornek_ag.yaml
```

## Kullanım

```bash
# Tüm cihaz ve kabloları dene, metin raporu ver
python -m zayifnokta ornekler/ornek_ag.yaml

# Aynı anda iki arıza senaryolarını da dene
python -m zayifnokta ornekler/ornek_ag.yaml --cift

# Raporu JSON ya da Markdown olarak dosyaya yaz
python -m zayifnokta ornekler/ornek_ag.yaml --cift --format json --cikti rapor.json
python -m zayifnokta ornekler/ornek_ag.yaml --cift --format markdown --cikti rapor.md

# Sadece tek bir cihaz için "bozulursa ne olur?"
python -m zayifnokta ornekler/ornek_ag.yaml --cihaz core-switch

# Graphviz çizimi için .dot dosyası (SPOF kırmızı, kapasite riski turuncu)
python -m zayifnokta ornekler/ornek_ag.yaml --dot ag.dot
dot -Tpng ag.dot -o ag.png      # Graphviz kuruluysa
```

## YAML biçimi

```yaml
giris_noktasi: internet-router      # kullanıcıların/internetin geldiği cihaz

cihazlar:
  - {isim: internet-router, tur: router}
  - {isim: sunucu-db, tur: sunucu, kapasite: 20}   # kapasite isteğe bağlı (yazılmazsa sınırsız)

baglantilar:                        # her satır bir kablo; aynı çifti iki kez yazarsan yedekli kablo olur
  - internet-router <-> sunucu-db

servisler:
  - isim: veritabani
    calistigi_yer: sunucu-db        # liste yazarsan servis yedekli sayılır: [sunucu-1, sunucu-2]
    ihtiyac_duydugu: [baska-servis] # isteğe bağlı
    onem: 5                         # 1-5 arası, varsayılan 3
    yuk: 8                          # isteğe bağlı; yedekler arasında eşit bölüşülür
```

Hazır bir örnek için `ornekler/ornek_ag.yaml` dosyasına bakın.

> **Gizlilik uyarısı:** `ornekler/` altındaki dosyalar uydurmadır. Kendi gerçek ağınız için hazırladığınız
> YAML dosyalarını `gercek/` klasörüne ya da `*.private.yaml` adıyla kaydedin; bunlar `.gitignore` ile
> GitHub'a yüklenmekten korunur. Ağınızın SPOF haritası, kötü niyetli biri için bir zayıflık haritasıdır.

## Nasıl çalışır?

1. YAML okunur ve kontrol edilir (tanımsız cihaz, yanlış bağlantı vb. için anlaşılır hata verilir).
2. Cihazlar nokta, kablolar çizgi olacak şekilde bir graf kurulur (NetworkX).
3. Her cihaz ve her kablo sırayla "bozuk" varsayılır, graftan çıkarılır.
4. `giris_noktasi`'ndan hâlâ ulaşılabilen cihazlar hesaplanır; ulaşılamayanlar "kopan" sayılır.
5. Bir servis, **yedeklerinden en az biri ulaşılabilir bir cihazda** çalışıyorsa ve **bağımlı olduğu tüm servisler ayaktaysa** çalışır sayılır.
6. **Kapasite:** ayaktaki her servisin `yuk` değeri, canlı yedekleri arasında eşit bölüşülür. Bir cihazın toplam yükü `kapasite` değerini aşarsa o cihaz "aşırı yüklü", üzerindeki servisler "yavaşlayan" sayılır.
7. **Çift arıza:** her bileşen çifti denenir. Yalnızca *tek tek bozulunca kaybolmayıp birlikte bozulunca kaybolan* servisler raporlanır; bunlar standart tek arıza analizinin göremediği gizli risklerdir.
8. **Risk:** kaybedilen servislerin `onem` toplamı (yavaşlayanlar yarım sayılır) toplam önem değerine oranlanır:
   `0% = YOK/DÜŞÜK`, `<25% DÜŞÜK`, `<50% ORTA`, `<75% YÜKSEK`, `75% ve üzeri KRİTİK`.

## Kendine özgü yanı

**Bu projenin kendine özgü kombinasyonu:** fiziksel ağ (cihaz + kablo) erişilebilirliği, yedekli servisler,
servisler arası bağımlılık, kapasite kontrolü ve çift arıza analizini tek, hafif, çevrimdışı bir
Türkçe CLI içinde birleştirmesidir. Tek tek bu parçaların hiçbiri yeni değildir.

## Testler

```bash
python -m unittest discover -s testler -v
```

## Sınırlamalar (bilerek basit tutuldu)

- Ağ, "cihaz çalışıyor mu, bağlantı var mı" düzeyinde modellenir. Bant genişliği, VLAN, yönlendirme protokolleri, ACL vb. dikkate alınmaz.
- Kapasite modeli basittir: yük yedekler arasında eşit bölünür, cihaz başına tek bir sayı kullanılır.
- En fazla iki eşzamanlı arıza denenir.
- Envanter elle yazılır; cihazlardan otomatik keşif yapılmaz.
- Büyük ağlarda `--cift` bileşen sayısının karesiyle yavaşlar (yüzlerce bileşene kadar sorunsuzdur).

## Geliştirme fikirleri

- Envanteri LLDP/SNMP veya Ansible envanterinden otomatik çıkarmak.
- Eşit olmayan yük dağılımı (ağırlıklı yedekler).
- CI'da kullanmak için "SPOF varsa hata kodu döndür" seçeneği.

## Lisans

MIT. Bkz. `LICENSE`.
