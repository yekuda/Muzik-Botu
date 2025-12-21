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
        self._manual_stop = False

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
            if not self.voice_client or not self.voice_client.is_connected(): return None
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
                
                if 'entries' in data: data = data['entries'][0]
                stream_url = data['url']
                self.current_title = data.get('title', 'Bilinmiyor')
                self.current_url = data.get('webpage_url', query if query.startswith("http") else None)
                self.duration = data.get('duration', 0)
                
                header_str = "".join([f"{k}: {v}\r\n" for k, v in data.get('http_headers', {}).items()])
                before_args = FFMPEG_OPTIONS['before_options'] + f' -headers "{header_str}" -ss {start_sec}'
                
                def after_playing(error):
                    if not self._manual_stop and self.loop_mode and self.current_url:
                        asyncio.run_coroutine_threadsafe(self.play_music(self.current_url), self.loop)

                source = discord.FFmpegPCMAudio(stream_url, executable=FFMPEG_PATH, before_options=before_args, options=FFMPEG_OPTIONS['options'])
                source = discord.PCMVolumeTransformer(source)
                source.volume = self.volume
                self.voice_client.play(source, after=after_playing)
                self.playback_start_time = time.time()
                return self.current_title
            except Exception as e:
                logger.error(e)
                self._manual_stop = False
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

        self.lbl_status = ctk.CTkLabel(self.sidebar_frame, text="Durum: Çevrimdışı", text_color="gray")
        self.lbl_status.grid(row=2, column=0, padx=20, pady=10)

        # Ses Kontrolü (Dikey, Sidebar'da)
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
        self.entry_search.bind("<Return>", lambda e: self.play_track()) # Enter tuşu ile çalma

        self.btn_search = ctk.CTkButton(self.main_frame, text="OYNAT", fg_color="transparent", border_width=2, text_color=("gray10", "#DCE4EE"), command=self.play_track)
        self.btn_search.pack(fill="x", pady=(0, 20))

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

        # Durdur butonu kaldırıldı
        
        self.switch_loop = ctk.CTkSwitch(self.controls_frame, text="Döngü", command=self.toggle_loop)
        self.switch_loop.pack(side="left", padx=20)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

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
            self.lbl_title.configure(text=bot.current_title)
        except: pass
        self.after(1000, self.update_ui_loop)

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

    def join_voice(self):
        owner_id = CONFIG.get('OWNER_ID', "")
        self.lbl_status.configure(text="Aranıyor...", text_color="orange")
        asyncio.run_coroutine_threadsafe(self.update_join_task(owner_id), bot.loop)

    async def update_join_task(self, user_id):
        name = await bot.join_user_channel(user_id)
        if name: self.lbl_status.configure(text=f"Bağlı: {name}", text_color="#3B8ED0")
        else: self.lbl_status.configure(text="Kanal bulunamadı", text_color="red")

    def play_track(self):
        query = self.entry_search.get()
        if query:
            self.lbl_status.configure(text="Yükleniyor...", text_color="orange")
            self.btn_play.configure(text="DURAKLAT ⏸", fg_color="#E67E22", hover_color="#D35400")
            asyncio.run_coroutine_threadsafe(self.update_info_task(query), bot.loop)

    async def update_info_task(self, query):
        title = await bot.play_music(query)
        if title: self.lbl_status.configure(text="Oynatılıyor", text_color="#3B8ED0")
        else: self.lbl_status.configure(text="Hata oluştu", text_color="red")

    def on_closing(self):
        try:
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