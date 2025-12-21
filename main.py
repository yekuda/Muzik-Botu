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

# --- KONFİGÜRASYON YÜKLEME ---
def load_config():
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("HATA: config.json dosyası bulunamadı! Lütfen config.example.json dosyasını kopyalayıp config.json yapın.")
        sys.exit(1)

CONFIG = load_config()
TOKEN = CONFIG['TOKEN']
FFMPEG_PATH = CONFIG.get('FFMPEG_PATH', r"C:\ffmpeg\bin\ffmpeg.exe") 

# --- LOGLAMA AYARI ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('MusicBot')

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch1'
}

# --- 1. BOT YAPISI ---
class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix="!", intents=intents)
        self.voice_client = None
        self.loop_mode = False
        self.current_url = None
        self.current_title = "Yok"
        self.volume = 1.0
        self.duration = 0
        self.start_offset = 0
        self.playback_start_time = 0
        self.accumulated_time = 0
        self.play_lock = asyncio.Lock()
        self._manual_stop = False # Döngü çakışmasını engellemek için kritik bayrak

    async def on_ready(self):
        print("\n" + "="*50)
        print(f"BOT AKTİF: {self.user}")
        print("="*50 + "\n")

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
            if not self.voice_client or not self.voice_client.is_connected():
                logger.error("HATA: Bot bir ses kanalında değil!")
                return None

            # Mevcut çalmayı durdururken döngüyü tetikleme
            if self.voice_client.is_playing() or self.voice_client.is_paused():
                self._manual_stop = True
                self.voice_client.stop()
                await asyncio.sleep(0.5)
                self._manual_stop = False

            self.start_offset = start_sec
            self.accumulated_time = 0

            try:
                loop = asyncio.get_event_loop()
                
                # Arama ve Veri Çekme
                search_str = query if query.startswith(("http://", "https://")) else f"ytsearch1:{query}"
                logger.info(f"---> İŞLENİYOR: {query}")

                with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                    data = await loop.run_in_executor(None, lambda: ydl.extract_info(search_str, download=False))
                
                if 'entries' in data:
                    data = data['entries'][0]
                
                stream_url = data['url']
                self.current_title = data.get('title', 'Bilinmiyor')
                self.current_url = data.get('webpage_url', query if query.startswith("http") else None)
                self.duration = data.get('duration', 0)
                
                # ffmpeg_path artık config'den geliyor
                headers = data.get('http_headers', {})
                header_str = "".join([f"{k}: {v}\r\n" for k, v in headers.items()])
                before_args = FFMPEG_OPTIONS['before_options'] + f' -headers "{header_str}" -ss {start_sec}'
                
                def after_playing(error):
                    if error: logger.error(f"Ffmpeg Hatası: {error}")
                    # Sadece şarkı gerçekten bittiyse ve döngü açıksa tekrar çal
                    if not self._manual_stop and self.loop_mode and self.current_url:
                        asyncio.run_coroutine_threadsafe(self.play_music(self.current_url), self.loop)

                source = discord.FFmpegPCMAudio(stream_url, executable=FFMPEG_PATH, before_options=before_args, options=FFMPEG_OPTIONS['options'])
                source = discord.PCMVolumeTransformer(source)
                source.volume = self.volume
                
                self.voice_client.play(source, after=after_playing)
                self.playback_start_time = time.time()
                
                print("\n" + "*"*50)
                print(f" BAŞARILI: {self.current_title}")
                print(f" SÜRE: {int(self.duration // 60)}:{int(self.duration % 60):02d}")
                print("*"*40 + "\n")
                
                return self.current_title
            except Exception as e:
                logger.error(f"SİSTEM HATASI: {e}")
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

# --- 2. ARAYÜZ (GUI) ---
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Antigravity Music")
        self.geometry("500x650")
        ctk.set_appearance_mode("Dark")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.main_frame = ctk.CTkFrame(self, corner_radius=20)
        self.main_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(self.main_frame, text="🎵 MUSIC CONTROL", font=("Outfit", 24, "bold"))
        self.title_label.pack(pady=(20, 5))
        
        self.status_label = ctk.CTkLabel(self.main_frame, text="Hazır", text_color="#555555", font=("Arial", 12))
        self.status_label.pack(pady=(0, 20))

        self.join_btn = ctk.CTkButton(self.main_frame, text="Beni Bul ve Katıl", command=self.join_voice, fg_color="#1DB954", height=40)
        self.join_btn.pack(fill="x", padx=30, pady=10)

        self.url_entry = ctk.CTkEntry(self.main_frame, placeholder_text="Şarkı Adı veya YouTube Linki...", height=45)
        self.url_entry.pack(fill="x", padx=30, pady=10)

        self.ctrl_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.ctrl_frame.pack(fill="x", padx=30, pady=10)
        
        self.play_btn = ctk.CTkButton(self.ctrl_frame, text="Oynat ▶", command=self.play_track, height=45)
        self.play_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))
        
        self.pause_btn = ctk.CTkButton(self.ctrl_frame, text="Duraklat ⏸", command=self.toggle_pause, fg_color="#F57C00", height=45)
        self.pause_btn.pack(side="left", expand=True, fill="x", padx=5)

        self.stop_btn = ctk.CTkButton(self.ctrl_frame, text="Durdur ⏹", command=self.stop_track, fg_color="#E91E63", height=45)
        self.stop_btn.pack(side="left", expand=True, fill="x", padx=(5, 0))

        self.seek_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.seek_frame.pack(fill="x", padx=30, pady=10)
        self.time_label = ctk.CTkLabel(self.seek_frame, text="00:00 / 00:00", font=("Arial", 11))
        self.time_label.pack()
        
        self.seek_slider = ctk.CTkSlider(self.seek_frame, from_=0, to=100, command=self.on_seek_drag)
        self.seek_slider.set(0)
        self.seek_slider.pack(fill="x", pady=5)
        self.seek_slider.bind("<Button-1>", lambda e: setattr(self, 'is_seeking', True))
        self.seek_slider.bind("<ButtonRelease-1>", self.on_seek_release)
        self.is_seeking = False

        self.volume_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.volume_frame.pack(fill="x", padx=30, pady=10)
        self.vol_label = ctk.CTkLabel(self.volume_frame, text="Ses: %100", font=("Arial", 12))
        self.vol_label.pack(side="left", padx=(0, 10))
        self.vol_slider = ctk.CTkSlider(self.volume_frame, from_=0, to=1, command=self.change_volume)
        self.vol_slider.set(1.0)
        self.vol_slider.pack(side="right", fill="x", expand=True)

        self.loop_switch = ctk.CTkSwitch(self.main_frame, text="Döngü (Loop)", command=self.toggle_loop, progress_color="#1DB954")
        self.loop_switch.pack(pady=20)

        self.info_label = ctk.CTkLabel(self.main_frame, text="Şu an çalan: -", font=("Arial", 11), text_color="gray")
        self.info_label.pack(pady=(0, 20))

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def update_ui_loop(self):
        try:
            if bot.voice_client and bot.voice_client.is_playing() and not self.is_seeking:
                elapsed = bot.get_elapsed_time()
                total = bot.duration
                if total > 0:
                    self.seek_slider.set((elapsed / total) * 100)
                    curr_min, curr_sec = divmod(elapsed, 60)
                    total_min, total_sec = divmod(total, 60)
                    self.time_label.configure(text=f"{curr_min:02d}:{curr_sec:02d} / {total_min:02d}:{total_sec:02d}")
        except: pass
        self.after(1000, self.update_ui_loop)

    def on_seek_drag(self, value):
        if bot.duration > 0:
            elapsed = int((value / 100) * bot.duration)
            curr_min, curr_sec = divmod(elapsed, 60)
            total_min, total_sec = divmod(bot.duration, 60)
            self.time_label.configure(text=f"{curr_min:02d}:{curr_sec:02d} / {total_min:02d}:{total_sec:02d}")

    def on_seek_release(self, event):
        value = self.seek_slider.get()
        if bot.current_url and bot.duration > 0:
            target_sec = int((value / 100) * bot.duration)
            asyncio.run_coroutine_threadsafe(bot.play_music(bot.current_url, start_sec=target_sec), bot.loop)
        self.after(500, lambda: setattr(self, 'is_seeking', False))

    def change_volume(self, value):
        self.vol_label.configure(text=f"Ses: %{int(value*100)}")
        asyncio.run_coroutine_threadsafe(bot.set_volume(value), bot.loop)

    def toggle_pause(self):
        if self.pause_btn.cget("text") == "Duraklat ⏸":
            asyncio.run_coroutine_threadsafe(bot.pause_music(), bot.loop)
            self.pause_btn.configure(text="Devam Et ▶", fg_color="#F9A825")
            self.status_label.configure(text="Duraklatıldı", text_color="#F57C00")
        else:
            asyncio.run_coroutine_threadsafe(bot.resume_music(), bot.loop)
            self.pause_btn.configure(text="Duraklat ⏸", fg_color="#F57C00")
            self.status_label.configure(text="Oynatılıyor", text_color="#1DB954")

    def toggle_loop(self):
        bot.loop_mode = self.loop_switch.get() == 1
        msg = "Döngü Aktif" if bot.loop_mode else "Döngü Devre Dışı"
        self.status_label.configure(text=msg, text_color="#1DB954" if bot.loop_mode else "#555555")

    def join_voice(self):
        my_id = "1219400194152464467"
        self.status_label.configure(text="Sizi arıyorum...", text_color="yellow")
        asyncio.run_coroutine_threadsafe(self.update_join_task(my_id), bot.loop)

    async def update_join_task(self, user_id):
        name = await bot.join_user_channel(user_id)
        if name: self.status_label.configure(text=f"Bağlı: {name}", text_color="#1DB954")
        else: self.status_label.configure(text="Kullanıcı bulunamadı!", text_color="#E91E63")

    def play_track(self):
        url = self.url_entry.get()
        if url:
            self.status_label.configure(text="Sorgulanıyor...", text_color="#1DB954")
            asyncio.run_coroutine_threadsafe(self.update_info_task(url), bot.loop)
    
    async def update_info_task(self, url):
        title = await bot.play_music(url)
        if title:
            self.info_label.configure(text=f"Şu an çalan: {title}")
            self.status_label.configure(text="Oynatılıyor", text_color="#1DB954")

    def stop_track(self):
        if bot.voice_client:
            bot._manual_stop = True # Durdurma butonuna basınca döngü çalışmasın
            bot.voice_client.stop()
            bot.current_url = None
            self.status_label.configure(text="Durduruldu", text_color="#E91E63")
            self.info_label.configure(text="Şu an çalan: -")
            # Bir saniye sonra bayrağı kapa
            threading.Timer(1.0, lambda: setattr(bot, '_manual_stop', False)).start()

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