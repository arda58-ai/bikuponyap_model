# GitHub'a yükleme

## 1. Lokal hazırlık (bir kez)

Proje kökünde (`bikuponyap_model/`):

```bash
cd /Users/yalcin/Desktop/bikuponyap_model

# Stage’i temizle, .gitignore’a göre tekrar ekle
git reset
git add .
git status   # Sadece kod ve dokümanların eklendiğini kontrol et

# İlk commit
git commit -m "Initial commit: Supersonic pipeline, puan durumu, standings API desteği"
```

## 2. GitHub’da repo oluştur

1. https://github.com/new adresine git.
2. Repository name: örn. `bikuponyap_model`.
3. Public veya Private seç.
4. **README, .gitignore, license ekleme** (lokal projede zaten var).
5. Create repository’e tıkla.

## 3. Remote ekleyip push et

GitHub’da repo oluşturduktan sonra sayfada gösterilen URL’i kullan (HTTPS veya SSH). Örnek (kendi kullanıcı adınla değiştir):

```bash
git remote add origin https://github.com/KULLANICI_ADIN/bikuponyap_model.git
git branch -M main
git push -u origin main
```

Şifre/erişim için: GitHub artık şifre kabul etmiyor; **Personal Access Token (PAT)** veya **SSH key** kullan.  
- Token: GitHub → Settings → Developer settings → Personal access tokens → Generate.  
- Push sırasında şifre yerine bu token’ı gir.

## 4. Sonraki güncellemeler

Kod değiştirdikten sonra:

```bash
git add .
git commit -m "Kısa açıklama"
git push
```

---

**Not:** `.gitignore` ile `data/processed/*.csv` ve `data/raw/` commit’lenmez (büyük veri, GitHub’a gerek yok). Repo sadece kaynak kod ve dokümanları içerir. Veriyi başka yerde sakla veya ayrı bir private depoda tut.
