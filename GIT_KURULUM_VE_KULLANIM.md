# Git kurulumu ve projeyi açma (sıfırdan)

İkinci PC’de Git yoksa veya hiç kullanmadıysan bu adımları sırayla uygula.

---

## 1. Git kurulumu

### macOS

**Yöntem A – Xcode Command Line Tools (önerilen)**  
Terminal’i aç (Spotlight: Cmd+Boşluk → “Terminal” yaz) ve çalıştır:

```bash
xcode-select --install
```

Açılan pencerede **Install** de. Kurulum bitince:

```bash
git --version
```

`git version 2.x.x` gibi bir çıktı görürsen kurulum tamam.

**Yöntem B – Homebrew ile**

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install git
git --version
```

### Windows

1. https://git-scm.com/download/win adresine git.
2. **Download** ile kurulum dosyasını indir, çalıştır.
3. Varsayılan seçeneklerle **Next** ile ilerle (PATH’e ekleme seçili kalsın).
4. Kurulum bitince **Git Bash** veya **CMD** açıp yaz:

```bash
git --version
```

---

## 2. Git’e kimlik tanıtma (ilk kez, bir kez yeterli)

Terminal’de (veya Git Bash’te):

```bash
git config --global user.name "Adın Soyadın"
git config --global user.email "github@eposta.com"
```

E-posta, GitHub hesabındaki e-posta ile aynı veya GitHub’da “Keep my email addresses private” kullanıyorsan GitHub’ın verdiği `...@users.noreply.github.com` adresi olsun.

---

## 3. GitHub Personal Access Token (push/pull için)

GitHub artık şifre ile push kabul etmiyor; **token** kullanacaksın.

1. Tarayıcıda GitHub’a gir → sağ üst **profil** → **Settings**.
2. Sol menüden **Developer settings** → **Personal access tokens** → **Tokens (classic)**.
3. **Generate new token** → **Generate new token (classic)**.
4. **Note:** örn. `bikuponyap_model PC2`.
5. **Expiration:** 90 days veya No expiration.
6. **Scopes:** **repo** kutusunu işaretle.
7. **Generate token** de.
8. Çıkan token’ı **hemen kopyala** (bir daha gösterilmez). Not defterine yapıştırıp sakla; şifre sorulduğunda bunu kullanacaksın.

---

## 4. Projeyi bilgisayara indirme (clone)

Projeyi koymak istediğin klasöre git. Örnek: Masaüstü.

**macOS / Linux (Terminal):**

```bash
cd ~/Desktop
git clone https://github.com/arda58-ai/bikuponyap_model.git
cd bikuponyap_model
```

**Windows (Git Bash veya CMD):**

```bash
cd Desktop
git clone https://github.com/arda58-ai/bikuponyap_model.git
cd bikuponyap_model
```

**Kimlik sorarsa:**

- **Username for 'https://github.com':** GitHub kullanıcı adın (örn. `arda58-ai`).
- **Password for 'https://...':** Az önce oluşturduğun **Personal Access Token**’ı yapıştır (yazarken görünmez, normal). Enter’a bas.

Clone başarılı olunca `bikuponyap_model` klasörü oluşur; içinde `src/`, `data/`, `.gitignore`, README vb. olur.

---

## 5. Python bağımlılıkları (projeyi çalıştırmak için)

```bash
cd bikuponyap_model
pip install pandas numpy lightgbm scikit-learn
```

(veya `pip3` kullanıyorsan: `pip3 install ...`)

---

## 6. Güncellemeleri almak (sen veya diğer kişi push yaptığında)

Proje klasöründe:

```bash
cd bikuponyap_model
git pull
```

Böylece GitHub’daki son değişiklikler bu PC’ye iner.

---

## 7. Değişiklik yapıp geri göndermek (push)

Kodda değişiklik yaptıktan sonra:

```bash
cd bikuponyap_model
git add .
git commit -m "Kısa açıklama"
git push
```

İlk push’ta yine **Username** ve **Password** (token) sorulabilir.

---

## Hızlı özet

| Adım | Komut / işlem |
|------|----------------|
| 1. Git kur | macOS: `xcode-select --install` veya `brew install git` |
| 2. Kimlik | `git config --global user.name "..."` ve `user.email "..."` |
| 3. Token | GitHub → Settings → Developer settings → Personal access tokens → Generate |
| 4. Projeyi indir | `git clone https://github.com/arda58-ai/bikuponyap_model.git` |
| 5. Bağımlılıklar | `pip install pandas numpy lightgbm scikit-learn` |
| Sonra: güncelleme al | `git pull` |
| Sonra: değişiklik gönder | `git add .` → `git commit -m "..."` → `git push` |

Takıldığın adımı söylersen oradan devam edebiliriz.
