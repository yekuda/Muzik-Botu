import threading
import asyncio
import discord
from discord.ext import commands
import customtkinter as ctk
import yt_dlp
import os
import time
import logging
import sys
import json
import hashlib
from pynput import keyboard
from pynput.keyboard import Key

# --- KONFİGÜRASYON ---
def load_config():
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        sys.exit(1)

CONFIG = load_config()
TOKEN = CONFIG['TOKEN']
FFMPEG_PATH = CONFIG.get('FFMPEG_PATH', r"C:\ffmpeg\bin\ffmpeg.exe")
CACHE_DIR = "songs_cache" 

# --- LOGLAMA ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger('MusicBot')

# --- AYARLAR ---
FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
YDL_OPTIONS = {'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True, 'no_warnings': True, 'default_search': 'ytsearch1'}

# --- BOT Sınıfı (Değişmedi, aynı stabilite) ---
class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix="!", intents=intents)
        self.voice_client = None
        self.loop_mode = False
        self.current_url = None
        self.current_title = "Beklemede..."
        self.volume = 1.0
        self.duration = 0
        self.start_offset = 0
        self.playback_start_time = 0
        self.accumulated_time = 0
        self.play_lock = asyncio.Lock()
        self.queue = [] # Şarkı sırası
        self.current_data = None # Tekrar çalma için veriyi sakla
        self._manual_stop = False
        self.is_playing_from_cache = False  # Cache'den mi çalıyor
        self.favorites = self.load_favorites()
        self.clean_orphaned_cache()
        self._cache_check_done = False  # Cache kontrolü yapıldı mı?

    def load_favorites(self):
        """Favorileri JSON'dan yükle"""
        try:
            with open('favorites.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def save_favorites(self):
        """Favorileri JSON'a kaydet"""
        try:
            with open('favorites.json', 'w', encoding='utf-8') as f:
                json.dump(self.favorites, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Favori kaydetme hatası: {e}")

    def get_cache_filename(self, url, title=None):
        """URL ve başlıktan cache dosya adı oluştur"""
        if title:
            # Başlığı dosya adı için güvenli hale getir
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_title = safe_title.replace(' ', '_')[:100]  # Max 100 karakter
            return f"{safe_title}.mp3"
        else:
            # Başlık yoksa hash kullan (fallback)
            url_hash = hashlib.md5(url.encode()).hexdigest()
            return f"{url_hash}.mp3"

    def get_cached_file_path(self, url, title=None):
        """Cache dosya yolunu döndür"""
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)
        return os.path.join(CACHE_DIR, self.get_cache_filename(url, title))

    def is_favorite_cached(self, url, title=None):
        """Favorinin cache'de olup olmadığını kontrol et"""
        cache_path = self.get_cached_file_path(url, title)
        return os.path.exists(cache_path)

    async def download_favorite_to_cache(self, url, title):
        """Favori şarkıyı cache'e indir"""
        try:
            cache_path = self.get_cached_file_path(url, title)
            
            # Zaten cache'de varsa indirme
            if os.path.exists(cache_path):
                return cache_path
            
            # yt-dlp ile indir (FFmpegExtractAudio .mp3 ekleyeceği için outtmpl'den .mp3'ü çıkar)
            cache_path_without_ext = cache_path.replace('.mp3', '')
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': cache_path_without_ext,
                'quiet': True,
                'no_warnings': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
            
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await loop.run_in_executor(None, lambda: ydl.download([url]))
            
            return cache_path
            
        except Exception as e:
            logger.error(f"Cache indirme hatası: {e}")
            return None

    def clean_orphaned_cache(self):
        """Favorilerde olmayan cache dosyalarını temizle"""
        try:
            if not os.path.exists(CACHE_DIR):
                return
            
            # Favorilerdeki dosya adlarını al
            valid_filenames = set()
            for fav in self.favorites:
                url = fav.get('url')
                title = fav.get('title')
                if url and title:
                    valid_filenames.add(self.get_cache_filename(url, title))
            
            # Cache klasöründeki dosyaları kontrol et
            cleaned = 0
            for filename in os.listdir(CACHE_DIR):
                if filename not in valid_filenames:
                    file_path = os.path.join(CACHE_DIR, filename)
                    try:
                        os.remove(file_path)
                        cleaned += 1
                    except Exception as e:
                        logger.error(f"Cache silme hatası: {e}")
            
            if cleaned > 0:
                logger.info(f"🧹 {cleaned} orphaned cache dosyası temizlendi")
                
        except Exception as e:
            logger.error(f"Cache temizleme hatası: {e}")

    def add_to_favorites(self):
        """Çalan şarkıyı favorilere ekle"""
        if not self.current_url or not self.current_title:
            return False
        
        # Zaten favorilerde mi kontrol et
        for fav in self.favorites:
            if fav.get('url') == self.current_url:
                return False  # Zaten var
        
        fav_data = {
            'title': self.current_title,
            'url': self.current_url,
            'duration': self.duration
        }
        self.favorites.append(fav_data)
        self.save_favorites()
        logger.info(f"⭐ Favorilere eklendi: {self.current_title}")
        
        # Cache'e indir (async olarak arka planda)
        asyncio.run_coroutine_threadsafe(
            self.download_favorite_to_cache(self.current_url, self.current_title),
            self.loop
        )
        
        return True

    def remove_from_favorites(self, url):
        """Favorilerden çıkar ve cache'i sil"""
        # Önce title'ı bul (silmeden önce)
        fav = next((f for f in self.favorites if f.get('url') == url), None)
        title = fav.get('title') if fav else None
        
        self.favorites = [f for f in self.favorites if f.get('url') != url]
        self.save_favorites()
        
        # Cache dosyasını sil
        try:
            cache_path = self.get_cached_file_path(url, title)
            if os.path.exists(cache_path):
                os.remove(cache_path)
                logger.info(f"🗑 Cache dosyası silindi")
        except Exception as e:
            logger.error(f"Cache silme hatası: {e}")

    async def check_favorites_cache(self):
        """Favorilerin cache'de olup olmadığını kontrol et ve eksikleri indir"""
        if not self.favorites:
            return
        
        logger.info(f"🔍 Favoriler kontrol ediliyor ({len(self.favorites)} adet)...")
        
        missing_count = 0
        cached_count = 0
        
        for fav in self.favorites:
            url = fav.get('url')
            title = fav.get('title')
            
            if not url or not title:
                continue
            
            # Cache'de var mı kontrol et
            if self.is_favorite_cached(url, title):
                cached_count += 1
            else:
                missing_count += 1
                # Arka planda indir
                await self.download_favorite_to_cache(url, title)
        
        if missing_count > 0:
            logger.info(f"✅ Cache hazır: {cached_count} mevcut, {missing_count} indirildi")


    async def on_ready(self):
        print(f"\n⚡ SİSTEM HAZIR: {self.user}\n")
        # Favorilerin cache kontrolünü yap
        if not self._cache_check_done:
            self._cache_check_done = True
            asyncio.create_task(self.check_favorites_cache())

    async def play_from_cache(self, url, title, duration, start_sec=0):
        """Cache'den direkt oynat"""
        try:
            cache_path = self.get_cached_file_path(url, title)
            
            if not os.path.exists(cache_path):
                logger.warning(f"Cache dosyası bulunamadı, stream'e geçiliyor")
                return await self.play_music(url, start_sec)
            
            # Bot bağlı değilse otomatik katıl
            if not self.voice_client or not self.voice_client.is_connected():
                owner_id = CONFIG.get('OWNER_ID', '')
                if owner_id:
                    logger.info("Bot bağlı değil, otomatik katılıyor...")
                    channel_name = await self.join_user_channel(owner_id)
                    if not channel_name:
                        logger.error("Kullanıcı ses kanalında değil!")
                        return None
                else:
                    logger.error("OWNER_ID config'de tanımlı değil!")
                    return None
            
            # Çalan varsa durdur
            if self.voice_client.is_playing() or self.voice_client.is_paused():
                self._manual_stop = True
                self.voice_client.stop()
                await asyncio.sleep(0.5)
                self._manual_stop = False
            
            self.current_title = title
            self.current_url = url
            self.duration = duration
            self.start_offset = start_sec
            self.accumulated_time = 0
            self.is_playing_from_cache = True  # Cache'den çalıyor
            
            logger.info(f"💾 Cache'den oynatılıyor: {title} (başlangıç: {start_sec}s)")
            
            def after_playing(error):
                if error: logger.error(f"HATA: {error}")
                if self._manual_stop: return

                # Döngü Açıksa -> Aynı şarkıyı tekrar başlat
                if self.loop_mode and self.current_data:
                    asyncio.run_coroutine_threadsafe(self._play_url(self.current_data), self.loop)
                # Sıra Varsa -> Sıradakine geç
                elif self.queue:
                    next_song = self.queue.pop(0)
                    asyncio.run_coroutine_threadsafe(self._play_url(next_song), self.loop)
                else:
                    self.current_title = "Beklemede..."
                    self.current_url = None
                    self.duration = 0
                    self.start_offset = 0
                    self.accumulated_time = 0
                    self.current_data = None
                    self.is_playing_from_cache = False
            
            # FFmpeg ile seek (local dosya için sadece -ss kullan, reconnect parametreleri stream için)
            before_args = f'-ss {start_sec}' if start_sec > 0 else ''
            if before_args:
                source = discord.FFmpegPCMAudio(cache_path, executable=FFMPEG_PATH, before_options=before_args, options=FFMPEG_OPTIONS['options'])
            else:
                source = discord.FFmpegPCMAudio(cache_path, executable=FFMPEG_PATH, options=FFMPEG_OPTIONS['options'])
            source = discord.PCMVolumeTransformer(source)
            source.volume = self.volume
            
            self.voice_client.play(source, after=after_playing)
            self.playback_start_time = time.time()
            
            return title
            
        except Exception as e:
            logger.error(f"Cache oynatma hatası: {e}")
            self.is_playing_from_cache = False
            return None

    async def join_user_channel(self, user_id):
        if not self.is_ready(): await self.wait_until_ready()
        for guild in self.guilds:
            member = guild.get_member(int(user_id))
            if member and member.voice:
                channel = member.voice.channel
                if self.voice_client and self.voice_client.is_connected():
                    await self.voice_client.move_to(channel)
                else:
                    self.voice_client = await channel.connect()
                return channel.name
        return None

    async def play_music(self, query, start_sec=0):
        async with self.play_lock:
            # EĞER BOT BAĞLI DEĞİLSE OTOMATIĞE KATIL
            if not self.voice_client or not self.voice_client.is_connected():
                owner_id = CONFIG.get('OWNER_ID', '')
                if owner_id:
                    logger.info("Bot bağlı değil, otomatik katlıyor...")
                    channel_name = await self.join_user_channel(owner_id)
                    if not channel_name:
                        logger.error("Kullanıcı ses kanalında değil!")
                        return None
                else:
                    logger.error("OWNER_ID config'de tanımlı değil!")
                    return None

            if self.voice_client.is_playing() or self.voice_client.is_paused():
                self._manual_stop = True
                self.voice_client.stop()
                await asyncio.sleep(0.5)
                self._manual_stop = False

            self.start_offset = start_sec
            self.accumulated_time = 0

            try:
                loop = asyncio.get_event_loop()
                search_str = query if query.startswith(("http://", "https://")) else f"ytsearch1:{query}"
                logger.info(f"Yükleniyor: {query}")

                with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                    data = await loop.run_in_executor(None, lambda: ydl.extract_info(search_str, download=False))
                
                # Arama sonuçlarını güvenli şekilde kontrol et
                if 'entries' in data:
                    if not data['entries'] or len(data['entries']) == 0:
                        logger.error("Arama sonuç bulunamadı!")
                        return None
                    data = data['entries'][0]
                
                # Veri geçerliliğini kontrol et
                if not data or 'url' not in data:
                    logger.error("Geçersiz video verisi!")
                    return None
                
                # DİREKT OYNAT (Mevcut şarkıyı durdur)
                return await self._play_url(data, start_sec)

            except Exception as e:
                logger.error(f"HATA: {e}")
                self._manual_stop = False
                return None

    async def _play_url(self, data, start_sec=0):
        self.current_data = data
        stream_url = data['url']
        self.current_title = data.get('title', 'Bilinmiyor')
        self.current_url = data.get('webpage_url', None)
        self.duration = data.get('duration', 0)
        self.is_playing_from_cache = False  # Stream'den çalıyor
        
        header_str = "".join([f"{k}: {v}\r\n" for k, v in data.get('http_headers', {}).items()])
        before_args = FFMPEG_OPTIONS['before_options'] + f' -headers "{header_str}" -ss {start_sec}'
        
        def after_playing(error):
            if error: logger.error(f"HATA: {error}")
            if self._manual_stop: return

            # Döngü Açıksa -> Aynı şarkıyı tekrar başlat
            if self.loop_mode and self.current_data:
                asyncio.run_coroutine_threadsafe(self._play_url(self.current_data), self.loop)
            # Sıra Varsa -> Sıradakine geç
            elif self.queue:
                next_song = self.queue.pop(0)
                asyncio.run_coroutine_threadsafe(self._play_url(next_song), self.loop)
            else:
                self.current_title = "Beklemede..."
                self.current_url = None
                self.duration = 0
                self.start_offset = 0
                self.accumulated_time = 0
                self.current_data = None

        source = discord.FFmpegPCMAudio(stream_url, executable=FFMPEG_PATH, before_options=before_args, options=FFMPEG_OPTIONS['options'])
        source = discord.PCMVolumeTransformer(source)
        source.volume = self.volume
        
        self.voice_client.play(source, after=after_playing)
        self.playback_start_time = time.time()
        return self.current_title

    async def skip_track(self):
        if self.voice_client and self.voice_client.is_playing():
            old_loop = self.loop_mode
            self.loop_mode = False 
            self.voice_client.stop()
            self.loop_mode = old_loop

    async def add_to_queue(self, query):
        """Şarkıyı sıraya ekle (çalmadan)"""
        try:
            loop = asyncio.get_event_loop()
            search_str = query if query.startswith(("http://", "https://")) else f"ytsearch1:{query}"
            logger.info(f"Sıraya ekleniyor: {query}")

            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                data = await loop.run_in_executor(None, lambda: ydl.extract_info(search_str, download=False))
            
            # Arama sonuçlarını güvenli şekilde kontrol et
            if 'entries' in data:
                if not data['entries'] or len(data['entries']) == 0:
                    logger.error("Arama sonuç bulunamadı!")
                    return None
                data = data['entries'][0]
            
            # Veri geçerliliğini kontrol et
            if not data or 'url' not in data:
                logger.error("Geçersiz video verisi!")
                return None
            
            self.queue.append(data)
            title = data.get('title', 'Bilinmiyor')
            logger.info(f"✓ Sıraya eklendi: {title}")
            # Durum çubuğu için kısaltılmış başlık
            short_title = title[:40] + "..." if len(title) > 40 else title
            return f"Sırada #{len(self.queue)}: {short_title}"
        except Exception as e:
            logger.error(f"Sıraya ekleme hatası: {e}")
            return None

    def get_elapsed_time(self):
        elapsed = self.accumulated_time + self.start_offset
        if self.voice_client and self.voice_client.is_playing():
            elapsed += (time.time() - self.playback_start_time)
        return int(elapsed)


    def pause_music(self):
        if self.voice_client and self.voice_client.is_playing():
            self.accumulated_time += (time.time() - self.playback_start_time)
            self.voice_client.pause()

    def resume_music(self):
        if self.voice_client and self.voice_client.is_paused():
            self.playback_start_time = time.time()
            self.voice_client.resume()

    async def set_volume(self, volume):
        self.volume = volume
        if self.voice_client and self.voice_client.source:
            self.voice_client.source.volume = volume

bot = MusicBot()

def run_bot_thread():
    bot.run(TOKEN)

# --- MEDYA TUŞU DİNLEYİCİSİ ---
class MediaKeyListener:
    def __init__(self, app_instance):
        self.app = app_instance
        self.listener = None
        self.last_press_time = 0  # Debounce için
        self.debounce_delay = 0.2  # 200ms minimum süre
        
        # Config'den hotkey'i oku
        hotkey_name = CONFIG.get('HOTKEY', 'home').lower()
        
        # Desteklenen tuşlar
        key_map = {
            'home': Key.home,
            'end': Key.end,
            'insert': Key.insert,
            'page_down': Key.page_down,
            'page_up': Key.page_up,
            'delete': Key.delete,
            'f1': Key.f1,
            'f2': Key.f2,
            'f3': Key.f3,
            'f4': Key.f4,
            'f5': Key.f5,
            'f6': Key.f6,
            'f7': Key.f7,
            'f8': Key.f8,
            'f9': Key.f9,
            'f10': Key.f10,
            'f11': Key.f11,
            'f12': Key.f12,
        }
        
        self.hotkey = key_map.get(hotkey_name, Key.home)
        logger.info(f"🎹 Hotkey ayarlandı: {hotkey_name.upper()}")
        
    def on_press(self, key):
        try:
            # Config'den okunan tuşu dinle
            if key == self.hotkey:
                # Debounce kontrolü
                current_time = time.time()
                if current_time - self.last_press_time < self.debounce_delay:
                    return  # Çok hızlı basılmış, yoksay
                
                self.last_press_time = current_time
                logger.info("⏯ Hotkey: Play/Pause")
                
                # Direkt bot fonksiyonunu çağır (hızlı - artık sync)
                if bot.voice_client:
                    if bot.voice_client.is_playing():
                        bot.pause_music()
                    elif bot.voice_client.is_paused():
                        bot.resume_music()
        except AttributeError:
            pass
    
    def start(self):
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()
        logger.info("⌨️ Medya tuşu dinleyicisi başlatıldı")
    
    def stop(self):
        if self.listener:
            self.listener.stop()

# --- 3. YENİ ARAYÜZ (Dashboard Style) ---
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Antigravity Control")
        self.geometry("700x500") # Geniş ve ferah
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("dark-blue") # Daha profesyonel mavi tonları

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- SOL PANEL (SIDEBAR) ---
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="ANTIGRAVITY", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.sidebar_button_1 = ctk.CTkButton(self.sidebar_frame, text="Bağlan / Katıl", command=self.join_voice)
        self.sidebar_button_1.grid(row=1, column=0, padx=20, pady=10)

        self.lbl_status = ctk.CTkLabel(self.sidebar_frame, text="Durum: Çevrimdışı", text_color="gray", wraplength=180)
        self.lbl_status.grid(row=2, column=0, padx=20, pady=10)

        # Sıra (Queue) Bölümü
        self.lbl_queue_title = ctk.CTkLabel(self.sidebar_frame, text="SIRA", font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_queue_title.grid(row=3, column=0, padx=20, pady=(20, 5), sticky="w")
        
        self.queue_textbox = ctk.CTkTextbox(self.sidebar_frame, height=200, width=180, fg_color=("gray90", "gray15"))
        self.queue_textbox.grid(row=4, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.queue_textbox.configure(state="disabled")  # Sadece okuma modu

        # Favoriler Bölümü
        self.lbl_fav_title = ctk.CTkLabel(self.sidebar_frame, text="FAVORİLER", font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_fav_title.grid(row=5, column=0, padx=20, pady=(10, 5), sticky="w")
        
        self.fav_textbox = ctk.CTkTextbox(self.sidebar_frame, height=150, width=180, fg_color=("gray90", "gray15"))
        self.fav_textbox.grid(row=6, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.fav_textbox.configure(state="disabled")
        self.fav_textbox.bind("<Button-1>", self.on_favorite_click)  # Sol tık: Çal
        self.fav_textbox.bind("<Button-3>", self.on_favorite_click)  # Sağ tık: Sil

        # Ses Kontrolü
        self.lbl_vol = ctk.CTkLabel(self.sidebar_frame, text="Ses Düzeyi")
        self.lbl_vol.grid(row=7, column=0, padx=20, pady=(10, 0))
        self.slider_vol = ctk.CTkSlider(self.sidebar_frame, from_=0, to=1, command=self.change_volume)
        self.slider_vol.grid(row=8, column=0, padx=20, pady=(0, 20))
        self.slider_vol.set(1.0)

        # --- SAĞ PANEL (CONTENT) ---
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_frame.grid_rowconfigure(2, weight=1)

        # Arama Kısmı
        self.entry_search = ctk.CTkEntry(self.main_frame, placeholder_text="Müzik ara veya link yapıştır...", height=40)
        self.entry_search.pack(fill="x", pady=(0, 10))
        self.entry_search.bind("<Return>", lambda e: self.play_track())

        # Buton Frame (Oynat ve Sıraya Ekle yan yana)
        self.search_btn_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.search_btn_frame.pack(fill="x", pady=(0, 20))
        
        self.btn_search = ctk.CTkButton(self.search_btn_frame, text="▶ OYNAT", fg_color="#3B8ED0", hover_color="#36719F", command=self.play_track)
        self.btn_search.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        self.btn_add_queue = ctk.CTkButton(self.search_btn_frame, text="+ SIRAYA EKLE", fg_color="transparent", border_width=2, border_color="gray", text_color="white", command=self.add_to_queue)
        self.btn_add_queue.pack(side="right", fill="x", expand=True, padx=(5, 0))

        # Şarkı Bilgi Kartı
        self.track_card = ctk.CTkFrame(self.main_frame, fg_color=("gray80", "gray20"))
        self.track_card.pack(fill="both", expand=True)
        
        self.lbl_playing = ctk.CTkLabel(self.track_card, text="ŞU AN ÇALINIYOR", font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_playing.pack(pady=(20, 0))
        
        self.lbl_title = ctk.CTkLabel(self.track_card, text="---", font=ctk.CTkFont(size=18), wraplength=400)
        self.lbl_title.pack(pady=10)

        self.lbl_timer = ctk.CTkLabel(self.track_card, text="00:00 / 00:00", font=ctk.CTkFont(family="monospace", size=14))
        self.lbl_timer.pack(pady=5)

        self.slider_seek = ctk.CTkSlider(self.track_card, from_=0, to=100, command=self.on_seek_drag, height=20)
        self.slider_seek.pack(fill="x", padx=40, pady=10)
        self.slider_seek.bind("<Button-1>", lambda e: setattr(self, 'is_seeking', True))
        self.slider_seek.bind("<ButtonRelease-1>", self.on_seek_release)
        self.is_seeking = False

        # Alt Kontroller
        self.controls_frame = ctk.CTkFrame(self.track_card, fg_color="transparent")
        self.controls_frame.pack(pady=20)

        # İşlevsiz prev butonu kaldırıldı

        self.btn_play = ctk.CTkButton(self.controls_frame, text="OYNAT ▶", width=120, height=40, 
                                      fg_color="#3B8ED0", hover_color="#36719F",
                                      command=self.toggle_pause)
        self.btn_play.pack(side="left", padx=20)
        
        self.btn_skip = ctk.CTkButton(self.controls_frame, text="⏭", width=50, height=40, 
                                      fg_color="transparent", border_width=1, border_color="gray", text_color="white",
                                      command=self.skip_track)
        self.btn_skip.pack(side="left", padx=10)
        
        self.btn_favorite = ctk.CTkButton(self.controls_frame, text="⭐", width=50, height=40,
                                         fg_color="transparent", border_width=1, border_color="gold", text_color="gold",
                                         command=self.toggle_favorite)
        self.btn_favorite.pack(side="left", padx=10)

        # Durdur butonu kaldırıldı
        
        self.switch_loop = ctk.CTkSwitch(self.controls_frame, text="Döngü", command=self.toggle_loop)
        self.switch_loop.pack(side="left", padx=20)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Medya tuşu dinleyicisini başlat
        self.media_listener = MediaKeyListener(self)
        self.media_listener.start()

    # --- FONKSİYONLAR ---
    def update_ui_loop(self):
        try:
            if bot.voice_client and bot.voice_client.is_playing() and not self.is_seeking:
                elapsed = bot.get_elapsed_time()
                total = bot.duration
                if total > 0:
                    self.slider_seek.set((elapsed / total) * 100)
                    e_m, e_s = divmod(elapsed, 60)
                    t_m, t_s = divmod(total, 60)
                    self.lbl_timer.configure(text=f"{e_m:02d}:{e_s:02d} / {t_m:02d}:{t_s:02d}")
            # Başlığı kısalt (max 60 karakter)
            title_text = bot.current_title[:60] + "..." if len(bot.current_title) > 60 else bot.current_title
            self.lbl_title.configure(text=title_text)
            self.update_queue_display()  # Sırayı sürekli güncelle
            self.update_favorites_display()  # Favorileri güncelle
        except: pass
        self.after(1000, self.update_ui_loop)

    def update_queue_display(self):
        """Sıra listesini güncelle"""
        self.queue_textbox.configure(state="normal")
        self.queue_textbox.delete("1.0", "end")
        
        if not bot.queue:
            self.queue_textbox.insert("1.0", "Sıra boş")
        else:
            for i, song_data in enumerate(bot.queue, 1):
                title = song_data.get('title', 'Bilinmiyor')[:35]  # Uzun başlıkları kısalt
                self.queue_textbox.insert("end", f"{i}. {title}\n")
        
        self.queue_textbox.configure(state="disabled")

    def update_favorites_display(self):
        """Favoriler listesini güncelle"""
        self.fav_textbox.configure(state="normal")
        self.fav_textbox.delete("1.0", "end")
        
        if not bot.favorites:
            self.fav_textbox.insert("1.0", "Favori yok\n\nÇalan şarkıyı ⭐ ile ekle")
        else:
            for i, fav in enumerate(bot.favorites, 1):
                title = fav.get('title', 'Bilinmiyor')[:30]
                self.fav_textbox.insert("end", f"{i}. {title}\n")
        
        self.fav_textbox.configure(state="disabled")

    def on_favorite_click(self, event):
        """Favorilerden tıklanan şarkıyı çal veya sil"""
        try:
            # Tıklanan satırı bul
            index = self.fav_textbox.index("@%s,%s" % (event.x, event.y))
            line_num = int(index.split('.')[0]) - 1
            
            if 0 <= line_num < len(bot.favorites):
                fav = bot.favorites[line_num]
                url = fav.get('url')
                title = fav.get('title', 'Bilinmiyor')
                duration = fav.get('duration', 0)
                
                if not url:
                    return
                
                # Sol tık: Çal
                if event.num == 1:  # Left click
                    self.lbl_status.configure(text="Favoriden yükleniyor...", text_color="gold")
                    
                    # Cache'de varsa cache'den çal, yoksa stream
                    if bot.is_favorite_cached(url, title):
                        asyncio.run_coroutine_threadsafe(
                            self.play_from_cache_task(url, title, duration), 
                            bot.loop
                        )
                    else:
                        asyncio.run_coroutine_threadsafe(
                            self.update_info_task(url), 
                            bot.loop
                        )
                
                # Sağ tık: Sil
                elif event.num == 3:  # Right click
                    # Onay penceresi göster
                    result = ctk.CTkInputDialog(
                        text=f"'{title[:40]}...' favorilerden silinsin mi?\n\n'evet' yazın:",
                        title="Favoriden Sil"
                    ).get_input()
                    
                    if result and result.lower() == 'evet':
                        bot.remove_from_favorites(url)
                        self.lbl_status.configure(text="Favorilerden silindi", text_color="orange")
                        logger.info(f"🗑 Favoriden silindi: {title}")
                        
        except Exception as e:
            logger.error(f"Favori tıklama hatası: {e}")

    def toggle_favorite(self):
        """Çalan şarkıyı favorilere ekle/çıkar"""
        if bot.add_to_favorites():
            self.lbl_status.configure(text="⭐ Favorilere eklendi", text_color="gold")
        else:
            self.lbl_status.configure(text="Zaten favorilerde", text_color="orange")

    def on_seek_drag(self, value):
        if bot.duration > 0:
            elapsed = int((value / 100) * bot.duration)
            e_m, e_s = divmod(elapsed, 60)
            self.lbl_timer.configure(text=f"{e_m:02d}:{e_s:02d} / --:--")

    def on_seek_release(self, event):
        value = self.slider_seek.get()
        if bot.current_url and bot.duration > 0:
            target_sec = int((value / 100) * bot.duration)
            
            # Cache'den çalıyorsa cache'den seek et
            if bot.is_playing_from_cache and bot.is_favorite_cached(bot.current_url, bot.current_title):
                # Favori bilgilerini bul
                fav = next((f for f in bot.favorites if f.get('url') == bot.current_url), None)
                if fav:
                    asyncio.run_coroutine_threadsafe(
                        bot.play_from_cache(bot.current_url, fav.get('title'), fav.get('duration', 0), start_sec=target_sec),
                        bot.loop
                    )
                else:
                    # Favori değilse stream'den seek et
                    asyncio.run_coroutine_threadsafe(bot.play_music(bot.current_url, start_sec=target_sec), bot.loop)
            else:
                # Stream'den çalıyorsa normal seek
                asyncio.run_coroutine_threadsafe(bot.play_music(bot.current_url, start_sec=target_sec), bot.loop)
                
        self.after(500, lambda: setattr(self, 'is_seeking', False))

    def change_volume(self, value):
        asyncio.run_coroutine_threadsafe(bot.set_volume(value), bot.loop)

    def toggle_pause(self):
        if self.btn_play.cget("text") == "DURAKLAT ⏸": 
            self.btn_play.configure(text="DEVAM ET ▶", fg_color="#3B8ED0", hover_color="#36719F")
            bot.pause_music()
        else:
            self.btn_play.configure(text="DURAKLAT ⏸", fg_color="#E67E22", hover_color="#D35400") # Turuncu tonları
            bot.resume_music()

    def toggle_loop(self):
        bot.loop_mode = bool(self.switch_loop.get())

    def stop_track(self):
        if bot.voice_client:
            bot._manual_stop = True
            bot.voice_client.stop()
            bot.current_url = None
            threading.Timer(1.0, lambda: setattr(bot, '_manual_stop', False)).start()
        self.btn_play.configure(text="OYNAT ▶", fg_color="#3B8ED0")
        self.slider_seek.set(0)
        self.lbl_timer.configure(text="00:00 / 00:00")

    
    def skip_track(self):
        asyncio.run_coroutine_threadsafe(bot.skip_track(), bot.loop)

    def join_voice(self):
        owner_id = CONFIG.get('OWNER_ID', "")
        self.lbl_status.configure(text="Aranıyor...", text_color="orange")
        asyncio.run_coroutine_threadsafe(self.update_join_task(owner_id), bot.loop)

    async def update_join_task(self, user_id):
        name = await bot.join_user_channel(user_id)
        if name: 
            # Kanal adını kısalt
            short_name = name[:25] + "..." if len(name) > 25 else name
            self.lbl_status.configure(text=f"Bağlı: {short_name}", text_color="#3B8ED0")
        else: 
            self.lbl_status.configure(text="Kanal bulunamadı", text_color="red")

    def add_to_queue(self):
        query = self.entry_search.get()
        if query:
            self.lbl_status.configure(text="Sıraya ekleniyor...", text_color="orange")
            asyncio.run_coroutine_threadsafe(self.update_queue_task(query), bot.loop)

    async def update_queue_task(self, query):
        result = await bot.add_to_queue(query)
        if result:
            # Mesajı kısalt (max 50 karakter)
            short_result = result[:50] + "..." if len(result) > 50 else result
            self.lbl_status.configure(text=short_result, text_color="#3B8ED0")
        else:
            self.lbl_status.configure(text="Sıraya eklenemedi", text_color="red")

    def play_track(self):
        query = self.entry_search.get()
        if query:
            self.lbl_status.configure(text="Yükleniyor...", text_color="orange")
            self.btn_play.configure(text="DURAKLAT ⏸", fg_color="#E67E22", hover_color="#D35400")
            asyncio.run_coroutine_threadsafe(self.update_info_task(query), bot.loop)

    async def update_info_task(self, query):
        title = await bot.play_music(query)
        if title:
            self.lbl_status.configure(text="Oynatılıyor", text_color="#3B8ED0")
        else:
            self.lbl_status.configure(text="Hata: Sonuç bulunamadı veya bağlantı yok", text_color="red")
            self.btn_play.configure(text="OYNAT ▶", fg_color="#3B8ED0")

    async def play_from_cache_task(self, url, title, duration):
        """Cache'den oynatma task'ı"""
        result = await bot.play_from_cache(url, title, duration)
        if result:
            self.lbl_status.configure(text="💾 Cache'den oynatılıyor", text_color="#3B8ED0")
            self.btn_play.configure(text="DURAKLAT ⏸", fg_color="#E67E22", hover_color="#D35400")
        else:
            self.lbl_status.configure(text="Cache hatası, stream'e geçildi", text_color="orange")

    def on_closing(self):
        try:
            # Medya dinleyiciyi durdur
            if hasattr(self, 'media_listener'):
                self.media_listener.stop()
            if bot.voice_client: asyncio.run_coroutine_threadsafe(bot.voice_client.disconnect(), bot.loop)
            asyncio.run_coroutine_threadsafe(bot.close(), bot.loop)
        except: pass
        self.destroy()
        os._exit(0)

if __name__ == "__main__":
    t = threading.Thread(target=run_bot_thread, daemon=True)
    t.start()
    app = App()
    app.after(1000, app.update_ui_loop)
    app.mainloop()