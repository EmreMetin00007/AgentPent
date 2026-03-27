# Release Guide

Bu repo için şu an manuel sürüm akışı kullanılıyor.

## Sürümleme

- `vMAJOR.MINOR.PATCH` biçimini kullan.
- Örnek: `v0.1.1`

## Yayın Öncesi Kontrol Listesi

1. `CHANGELOG.md` dosyasındaki `Unreleased` bölümünü güncelle.
2. Gerekliyse sürüm referanslarını güncelle.
3. Testleri çalıştır:

```bash
python -m pytest
```

4. Değişiklikleri commit et.
5. Etiketi oluştur:

```bash
git tag v0.1.1
```

6. Branch ve tag'i gönder:

```bash
git push origin main
git push origin v0.1.1
```

7. GitHub üzerinde tag'den bir Release oluştur ve `CHANGELOG.md` notlarını kullan.

## Sürüm Referansları

Bugün için sürüm metni iki yerde elle tutuluyor:

- `cli/main.py`
- `core/report_generator.py`

İstersen sonraki adımda bunu merkezi bir `VERSION` dosyasına bağlayabiliriz.
