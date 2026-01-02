# Antigravity Music Bot

Modern bir grafik kullanıcı arayüzüne sahip kapsamlı bir Discord müzik botu uygulaması. Bu uygulama, YouTube ses akışını, yerel önbelleğe almayı ve güvenilir oynatma kontrollerini bağımsız bir masaüstü kontrol panelinde birleştirir. Kullanıcıların Discord ses kanalına bağlıyken müzik çalmayı, sıraları ve favorileri doğrudan masaüstünden yönetmesine olanak tanır.

## Özellikler

### Temel Fonksiyonlar
- **YouTube Entegrasyonu**: Doğrudan YouTube üzerinden URL veya arama sorguları ile müzik arama ve oynatma.
- **Sıra Sistemi**: Otomatik sıralı oynatma ile şarkı listesi yönetimi.
- **Favoriler ve Önbellekleme**: Sık çalınan şarkıları favoriler listesine kaydetme. Favorilenen şarkılar, gelecekteki oturumlarda anında ve takılmadan çalınması için otomatik olarak indirilir ve yerel olarak önbelleğe alınır.
- **Döngü Modu**: Geçerli parçayı veya sırayı tekrar etmek için döngü modu.

### Kullanıcı Arayüzü ve Kontroller
- **Modern Kontrol Paneli**: CustomTkinter ile oluşturulmuş, koyu temalı ve duyarlı bir arayüz.
- **Oynatma Kontrolleri**: Oynat, duraklat, atla, durdur ve ses seviyesi ayarlama kontrolleri.
- **İlerleme Çubuğu**: Parça içinde belirli zaman damgalarına gitmek için etkileşimli ilerleme çubuğu.
- **Global Kısayol Tuşları**: Uygulama arka plandayken bile oynatmayı/duraklatmayı kontrol etmek için yapılandırılabilir global kısayol tuşları (varsayılan: Home tuşu).
- **Gerçek Zamanlı Durum**: Parça süresi, geçen süre ve bağlantı durumu için canlı güncellemeler.

### Metin Okuma (TTS)
- **Çoklu Dil Desteği**: Türkçe ve İngilizce için entegre Edge-TTS desteği.
- **Otomatik Dil Algılama**: Uygun ses modelini seçmek için giriş metni dilinin akıllı tespiti.
- **Kesintisiz Entegrasyon**: TTS duyuruları için müziği otomatik olarak duraklatır ve sonrasında kaldığı yerden devam eder.

### Teknik ve Performans
- **FFmpeg Ses İşleme**: Yüksek kaliteli ses kodlama ve akışı.
- **İş Parçacıklı Mimari**: Arka plan iş parçacıklarında ağ isteklerini ve ses işlemeyi yönetirken arayüzün yanıt vermesini sağlayan yapı.
- **Önbellek Temizliği**: Kullanılmayan dosyaları kaldırmak için önbellek dizininin otomatik bakımı.
- **Hata Yönetimi**: Ağ sorunları ve geçersiz girişler için sağlam hata yönetimi.

## Gereksinimler

- Python 3.10 veya üzeri
- FFmpeg (Ses işleme için gerekli)
- Discord Bot Tokeni
- Windows İşletim Sistemi

## Kurulum

1. **Depoyu Klonlayın**
   ```bash
   git clone https://github.com/yakupemreyerli/Muzik-Botu.git
   cd Muzik-Botu
   ```

2. **Bağımlılıkları Yükleyin**
   ```bash
   pip install -r requirements.txt
   ```

3. **FFmpeg Kurulumu**
   - FFmpeg sürümünü indirin.
   - Bilinen bir konuma çıkartın (örneğin: `C:\ffmpeg`).
   - `ffmpeg.exe` dosyasının erişilebilir olduğundan emin olun.

4. **Yapılandırma**
   Ana dizinde `config.example.json` dosyasından kopyalayarak bir `config.json` dosyası oluşturun:
   ```json
   {
       "TOKEN": "DISCORD_BOT_TOKENINIZ",
       "FFMPEG_PATH": "C:\\ffmpeg\\bin\\ffmpeg.exe",
       "OWNER_ID": "DISCORD_KULLANICI_IDNIZ",
       "HOTKEY": "home",
       "PREFIX": "!",
       "TTS": {
           "VOICE_TR": "tr-TR-EmelNeural",
           "VOICE_EN": "en-US-AriaNeural"
       }
   }
   ```
   - **TOKEN**: Discord Bot Tokeniniz.
   - **FFMPEG_PATH**: FFmpeg yürütülebilir dosyasının tam yolu.
   - **OWNER_ID**: Discord Kullanıcı ID'niz (otomatik katılma için kullanılır).
   - **HOTKEY**: Oynat/duraklat için global tuş (örneğin: 'home', 'f1', 'insert').

## Kullanım

1. **Uygulamayı Başlatın**
   ```bash
   python main.py
   ```

2. **Discord'a Bağlanın**
   - Discord'da bir ses kanalına katılın.
   - Uygulama yan panelindeki **Bağlan** düğmesine tıklayın.

3. **Müzik Çalma**
   - Arama çubuğuna bir şarkı adı veya YouTube bağlantısı girin.
   - **Oynat** veya **Sıraya Ekle** düğmesine tıklayın.

4. **Favorileri Yönetme**
   - Geçerli parçayı favorilere eklemek için Yıldız simgesine tıklayın.
   - Anında çalmak için yan paneldeki bir favori öğesine sol tıklayın.
   - Kaldırmak için bir favori öğesine sağ tıklayın.

5. **Metin Okuma (TTS) Kullanımı**
   - TTS giriş alanına metin girin.
   - Dili seçin (Otomatik, TR veya EN).
   - Mesajı kanalda yayınlamak için Konuş düğmesine tıklayın.

## Sorun Giderme

- **FFmpeg Bulunamadı**: `config.json` dosyasındaki `FFMPEG_PATH` değerinin doğru yürütülebilir dosya konumunu gösterdiğinden emin olun.
- **Bot Katılmıyor**: `OWNER_ID` değerinin Discord ID'nizle eşleştiğinden ve bir ses kanalında olduğunuzdan emin olun.
- **Arama Hataları**: İnternet bağlantınızı kontrol edin ve arama sorgusunun geçerli olduğundan emin olun.
