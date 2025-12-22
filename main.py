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
        self.favorites = self.load_favorites()

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
        return True

    def remove_from_favorites(self, url):
        """Favorilerden çıkar"""
        self.favorites = [f for f in self.favorites if f.get('url') != url]
        self.save_favorites()

    async def on_ready(self):
        print(f"\n⚡ SİSTEM HAZIR: {self.user}\n")

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

    async def pause_music(self):
        if self.voice_client and self.voice_client.is_playing():
            self.accumulated_time += (time.time() - self.playback_start_time)
            self.voice_client.pause()

    async def resume_music(self):
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
                logger.info("⏯ Hotkey: Play/Pause")
                # Direkt bot fonksiyonunu çağır (hızlı)
                if bot.voice_client:
                    if bot.voice_client.is_playing():
                        asyncio.run_coroutine_threadsafe(bot.pause_music(), bot.loop)
                    elif bot.voice_client.is_paused():
                        asyncio.run_coroutine_threadsafe(bot.resume_music(), bot.loop)
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
        self.fav_textbox.bind("<Button-1>", self.on_favorite_click)

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
        """Favorilerden tıklanan şarkıyı çal"""
        try:
            # Tıklanan satırı bul
            index = self.fav_textbox.index("@%s,%s" % (event.x, event.y))
            line_num = int(index.split('.')[0]) - 1
            
            if 0 <= line_num < len(bot.favorites):
                fav = bot.favorites[line_num]
                url = fav.get('url')
                if url:
                    self.lbl_status.configure(text="Favoriden yükleniyor...", text_color="gold")
                    asyncio.run_coroutine_threadsafe(self.update_info_task(url), bot.loop)
        except: pass

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
            asyncio.run_coroutine_threadsafe(bot.play_music(bot.current_url, start_sec=target_sec), bot.loop)
        self.after(500, lambda: setattr(self, 'is_seeking', False))

    def change_volume(self, value):
        asyncio.run_coroutine_threadsafe(bot.set_volume(value), bot.loop)

    def toggle_pause(self):
        if self.btn_play.cget("text") == "DURAKLAT ⏸": 
            self.btn_play.configure(text="DEVAM ET ▶", fg_color="#3B8ED0", hover_color="#36719F")
            asyncio.run_coroutine_threadsafe(bot.pause_music(), bot.loop)
        else:
            self.btn_play.configure(text="DURAKLAT ⏸", fg_color="#E67E22", hover_color="#D35400") # Turuncu tonları
            asyncio.run_coroutine_threadsafe(bot.resume_music(), bot.loop)

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