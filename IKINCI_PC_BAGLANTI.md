# İkinci PC’yi repoya bağlama

İkinci bilgisayarda projeyi açıp seninle aynı repoda çalışmak için adımlar.

---

## 1. GitHub’da davet (sadece ikinci kişi farklı hesapla girecekse)

- **Sen (repo sahibi):** GitHub → **arda58-ai/bikuponyap_model** → **Settings** → **Collaborators** → **Add people** → ikinci PC’yi kullanacak kişinin GitHub kullanıcı adı veya e-postası → davet gönder.
- **O kişi:** E-postadaki daveti kabul etsin.
- İkinci PC’de kendi GitHub hesabınla gireceksen bu adım gerekmez.

---

## 2. İkinci PC’de (ilk kurulum)

### Git kurulu mu?

```bash
git --version
```

Yoksa: https://git-scm.com/downloads veya macOS’ta `xcode-select --install`.

### Projeyi indir (clone)

İndirmek istediğin klasöre git (örn. Masaüstü), sonra:

```bash
git clone https://github.com/arda58-ai/bikuponyap_model.git
cd bikuponyap_model
```

**Kimlik sorarsa:**

- **Username:** GitHub kullanıcı adı (ikinci PC’de giren hesap: `arda58-ai` veya davet edilen kişinin kullanıcı adı).
- **Password:** **Personal Access Token** (hesap şifresi değil).  
  Token yoksa: GitHub → **Settings** → **Developer settings** → **Personal access tokens** → **Generate new token (classic)** → **repo** işaretle → oluştur → kopyala, şifre yerine yapıştır.

### Python bağımlılıkları

```bash
pip install pandas numpy lightgbm scikit-learn
```

(İstersen `requirements.txt` varsa: `pip install -r requirements.txt`.)

---

## 3. Güncellemeleri almak (sen push yaptıktan sonra)

İkinci PC’de proje klasöründe:

```bash
cd bikuponyap_model
git pull
```

Böylece senin yüklediğin son commit’ler indirilir.

---

## 4. İkinci PC’de değişiklik yapıp geri göndermek

```bash
git add .
git commit -m "Kısa açıklama"
git push
```

İlk push’ta yine **Username** + **Token** (şifre yerine) sorulabilir.

---

## Özet

| Ne yapılıyor      | Komut / işlem                          |
|-------------------|----------------------------------------|
| İlk kez projeyi al | `git clone https://github.com/arda58-ai/bikuponyap_model.git` |
| Son kodu al      | `git pull`                             |
| Değişiklik gönder | `git add .` → `git commit -m "..."` → `git push` |
| Kimlik           | Kullanıcı adı + **Personal Access Token** (şifre değil) |

İkinci PC böyle aynı repoya bağlanır; sen push, o pull (ve tersi) ile birlikte çalışırsınız.
