# 🎵 Antigravity Music Bot

Modern ve kullanıcı dostu arayüze sahip Discord müzik botu. YouTube'dan müzik arama, çalma ve yönetme özellikleriyle donatılmış masaüstü uygulaması.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Discord.py](https://img.shields.io/badge/Discord.py-2.0+-7289DA.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## ✨ Özellikler

### 🎶 Müzik Yönetimi
- **YouTube Arama & Link Desteği**: Şarkı adı veya direkt YouTube linki ile çalma
- **Sıra (Queue) Sistemi**: Şarkıları sıraya ekle, otomatik sırayla çal
- **Favoriler**: Beğendiğin şarkıları kaydet, hızlıca tekrar çal
- **Döngü (Loop) Modu**: Şarkıyı veya listeyi sürekli tekrarla
- **Atla (Skip)**: Sıradaki şarkıya geç

### 🎛️ Oynatma Kontrolleri
- **Oynat/Duraklat**: Dinamik buton ile kolay kontrol
- **İleri/Geri Sarma**: Seek bar ile şarkının istediğin yerine git
- **Ses Seviyesi**: Anlık ses kontrolü
- **Otomatik Bağlanma**: Bot açılınca otomatik ses kanalına katıl

### 🎨 Modern Arayüz
- **Karanlık Tema**: Göz yormayan profesyonel tasarım
- **Canlı Sıra Görünümü**: Sol panelde sıradaki şarkıları gör
- **Favoriler Listesi**: Kayıtlı şarkılarını tek tıkla çal
- **Durum Bildirimleri**: Her işlem için net geri bildirim
- **Responsive Tasarım**: Uzun şarkı adları otomatik kısaltılır

### 🔧 Teknik Özellikler
- **Güvenli Arama**: Hata yakalama ve kullanıcı bildirimleri
- **JSON Tabanlı Ayarlar**: Kolay yapılandırma sistemi
- **Kalıcı Favoriler**: Favorilerin kapansa bile kaybolmaz
- **Çoklu Thread Desteği**: Bot ve arayüz ayrı çalışır

## 📋 Gereksinimler

- Python 3.10 veya üzeri
- FFmpeg (ses işleme için)
- Discord Bot Token
- Windows işletim sistemi (şu an için)

## 🚀 Kurulum

### 1. Projeyi İndir
```bash
git clone https://github.com/yekuda/Muzik-Botu.git
cd Muzik-Botu
```

### 2. Gerekli Kütüphaneleri Yükle
```bash
pip install -r requirements.txt
```

### 3. FFmpeg Kurulumu
1. [FFmpeg'i indir](https://ffmpeg.org/download.html)
2. `C:\ffmpeg\bin\` klasörüne çıkar
3. Veya farklı bir yere kurduysanız `config.json` dosyasında yolu güncelleyin

### 4. Discord Bot Oluştur
1. [Discord Developer Portal](https://discord.com/developers/applications)'a git
2. "New Application" ile yeni bir uygulama oluştur
3. "Bot" sekmesinden bot oluştur ve **Token**'ı kopyala
4. "OAuth2" > "URL Generator" kısmından:
   - **Scopes**: `bot`
   - **Bot Permissions**: `Connect`, `Speak`, `Use Voice Activity`
5. Oluşan linki tarayıcıda aç ve botu sunucuna ekle

### 5. Yapılandırma
`config.example.json` dosyasını `config.json` olarak kopyala ve düzenle:

```json
{
    "TOKEN": "BURAYA_BOT_TOKENINI_YAPISTIR",
    "FFMPEG_PATH": "C:\\ffmpeg\\bin\\ffmpeg.exe",
    "OWNER_ID": "DISCORD_KULLANICI_ID_N"
}
```

**Discord ID'ni Öğrenme:**
1. Discord ayarlarından "Gelişmiş" > "Geliştirici Modu"nu aç
2. Profiline sağ tıkla > "Kullanıcı ID'sini Kopyala"

### 6. Çalıştır
```bash
python main.py
```

## 🎮 Kullanım

### İlk Başlatma
1. Uygulamayı çalıştır
2. Discord'da bir ses kanalına gir
3. "Bağlan / Katıl" butonuna bas (veya direkt şarkı ara, otomatik bağlanır)

### Şarkı Çalma
1. **Arama kutusuna** şarkı adı veya YouTube linki yaz
2. **▶ OYNAT** butonuna bas → Hemen çalar
3. **+ SIRAYA EKLE** butonuna bas → Sıraya eklenir

### Favorilere Ekleme
1. Bir şarkı çalarken **⭐** butonuna bas
2. Sol panelde "FAVORİLER" bölümünde görünür
3. Favoriden çalmak için üzerine tıkla

### Sıra Yönetimi
- **Sıra** bölümünde şarkılar otomatik güncellenir
- **⏭ Atla** butonu ile sıradakine geç
- Şarkı bitince otomatik sıradaki çalar

### Kontroller
- **OYNAT/DURAKLAT**: Müziği durdur/devam ettir
- **Seek Bar**: Şarkının istediğin yerine git
- **Ses Düzeyi**: Sol panelde ses seviyesini ayarla
- **Döngü**: Aynı şarkıyı tekrarla

## 📁 Dosya Yapısı

```
Muzik-Botu/
├── main.py                 # Ana uygulama
├── config.json            # Kullanıcı ayarları (gitignore'da)
├── config.example.json    # Ayar şablonu
├── favorites.json         # Favori şarkılar (gitignore'da)
├── requirements.txt       # Python bağımlılıkları
├── .gitignore            # Git hariç tutma listesi
└── README.md             # Bu dosya
```

## 🛠️ Teknolojiler

- **[Discord.py](https://github.com/Rapptz/discord.py)**: Discord bot framework
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)**: YouTube video/ses indirme
- **[CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)**: Modern GUI framework
- **[FFmpeg](https://ffmpeg.org/)**: Ses işleme ve streaming
- **[asyncio](https://docs.python.org/3/library/asyncio.html)**: Asenkron işlemler

## 🐛 Bilinen Sorunlar ve Çözümler

### "HATA: Sonuç bulunamadı"
- YouTube'da gerçekten böyle bir şarkı var mı kontrol et
- İnternet bağlantını kontrol et
- Farklı arama terimleri dene

### "Bot bağlı değil" Hatası
- Discord'da bir ses kanalında olduğundan emin ol
- `config.json` dosyasındaki `OWNER_ID` doğru mu kontrol et
- Botu sunucudan at ve tekrar davet et

### FFmpeg Bulunamadı
- FFmpeg'in doğru yere kurulduğundan emin ol
- `config.json` dosyasındaki `FFMPEG_PATH` yolunu kontrol et

### Şarkı Çalmıyor
- Bot ses kanalında mı kontrol et
- FFmpeg yolu doğru mu kontrol et
- Terminal/konsoldaki hata mesajlarını oku

## 🔐 Güvenlik

- ⚠️ **Asla** `config.json` dosyasını paylaşma (bot token'ı içerir)
- ⚠️ Bot token'ı GitHub'a yükleme (`.gitignore` ile korunuyor)
- ⚠️ Token'ın sızdığını düşünüyorsan Discord Developer Portal'dan yenile

## 📝 Lisans

Bu proje MIT lisansı altında lisanslanmıştır. Detaylar için [LICENSE](LICENSE) dosyasına bakın.

## 🤝 Katkıda Bulunma

1. Bu repo'yu fork'la
2. Yeni bir branch oluştur (`git checkout -b feature/yeniOzellik`)
3. Değişikliklerini commit'le (`git commit -m 'Yeni özellik eklendi'`)
4. Branch'ini push'la (`git push origin feature/yeniOzellik`)
5. Pull Request oluştur

## 📧 İletişim

Sorularınız veya önerileriniz için [Issues](https://github.com/yekuda/Muzik-Botu/issues) bölümünü kullanabilirsiniz.

## 🎉 Teşekkürler

Bu projeyi kullandığınız için teşekkürler! Beğendiyseniz ⭐ vermeyi unutmayın!

---

**Not**: Bu bot sadece eğitim amaçlıdır. YouTube'un kullanım şartlarına uygun şekilde kullanın.
