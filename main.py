import os, sys, threading, shutil, webbrowser, platform, traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import ttkbootstrap as tb
from yt_dlp import YoutubeDL

# --- OSごとの日本語フォント設定 ---
system = platform.system()
if system == "Windows":
    FONT_FAMILY = "Meiryo"
elif system == "Darwin":
    FONT_FAMILY = "Hiragino Sans"
else:
    FONT_FAMILY = "Noto Sans CJK JP"

LABEL_FONT = (FONT_FAMILY, 11)
ENTRY_FONT = (FONT_FAMILY, 10)
BUTTON_FONT = (FONT_FAMILY, 10)

DOWNLOAD_FOLDER = os.path.join(os.path.expanduser("~"), "Downloads")

# --- ffmpeg のパス設定 ---
def get_ffmpeg_path():
    if getattr(sys, 'frozen', False):
        # PyInstaller バンドル時
        exe_name = "ffmpeg.exe" if system=="Windows" else "ffmpeg"
        return os.path.join(sys._MEIPASS, exe_name)
    else:
        return shutil.which("ffmpeg")

# --- ログ挿入関数 ---
MAX_LOG_LINES = 800
def safe_insert_log(text_widget: tk.Text, msg: str):
    def _insert():
        text_widget.insert(tk.END, msg + "\n")
        text_widget.see(tk.END)
        num_lines = int(text_widget.index('end-1c').split('.')[0])
        if num_lines > MAX_LOG_LINES:
            text_widget.delete("1.0", f"{num_lines-MAX_LOG_LINES+1}.0")
    text_widget.after(0, _insert)

# --- Logger for yt-dlp ---
class LoggerRedirect:
    def __init__(self, text_widget: tk.Text):
        self.text_widget = text_widget
    def debug(self, msg): pass
    def info(self, msg): safe_insert_log(self.text_widget, f"[INFO] {msg}")
    def warning(self, msg): safe_insert_log(self.text_widget, f"[WARN] {msg}")
    def error(self, msg): safe_insert_log(self.text_widget, f"[ERROR] {msg}")

# --- GUI setup ---
app = tb.Window(themename="darkly")
app.title("ytdlp manager")
app.geometry("720x600")

# --- ttkスタイル設定 ---
style = ttk.Style()
style.configure("My.TButton", font=BUTTON_FONT)
style.configure("My.TRadiobutton", font=BUTTON_FONT)

main_frame = ttk.Frame(app, padding=12)
main_frame.pack(fill=tk.BOTH, expand=True)

# --- URL入力（複数行対応） ---
ttk.Label(main_frame, text="動画URL（改行で複数指定可）", font=LABEL_FONT).pack(anchor="w")
url_text = tk.Text(main_frame, height=4, font=ENTRY_FONT)
url_text.pack(fill=tk.X, pady=(2, 6))

# --- 保存先 ---
ttk.Label(main_frame, text="保存先フォルダ", font=LABEL_FONT).pack(anchor="w", pady=(6,2))
folder_var = tk.StringVar(value=DOWNLOAD_FOLDER)
folder_frame = ttk.Frame(main_frame)
folder_frame.pack(fill=tk.X, pady=(0,6))
folder_entry = ttk.Entry(folder_frame, textvariable=folder_var, font=ENTRY_FONT)
folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
def select_folder():
    folder_selected = filedialog.askdirectory(initialdir=folder_var.get() or DOWNLOAD_FOLDER)
    if folder_selected: folder_var.set(folder_selected)
folder_btn = ttk.Button(folder_frame, text="選択", command=select_folder, style="My.TButton")
folder_btn.pack(side=tk.LEFT, padx=6)
open_folder_btn = ttk.Button(folder_frame, text="フォルダを開く", command=lambda: webbrowser.open(folder_var.get()), style="My.TButton")
open_folder_btn.pack(side=tk.LEFT)

# --- フォーマット選択 ---
format_frame = ttk.Frame(main_frame)
format_frame.pack(fill=tk.X, pady=(4,4))
format_var = tk.StringVar(value="mp4")

video_quality_list = [
    "bestvideo+bestaudio/best  (最高画質)",
    "best[height<=1080]+bestaudio/best  (1080pまで)",
    "best[height<=720]+bestaudio/best   (720pまで)",
    "best[height<=480]+bestaudio/best   (480pまで)",
]
audio_quality_list = [
    "bestaudio  (最高音質)",
    "worst  (最低音質)"
]

quality_frame = ttk.Frame(main_frame)
quality_frame.pack(fill=tk.X, pady=(2,6))
ttk.Label(quality_frame, text="品質:", font=LABEL_FONT).pack(side=tk.LEFT)
quality_var = tk.StringVar(value=video_quality_list[0])
quality_combo = ttk.Combobox(
    quality_frame,
    textvariable=quality_var,
    state="readonly",
    width=40,
    values=video_quality_list,
    font=ENTRY_FONT
)
quality_combo.pack(side=tk.LEFT, padx=6)

def update_quality_options():
    if format_var.get() == "mp4":
        quality_combo.config(values=video_quality_list)
        quality_combo.set(video_quality_list[0])
    else:
        quality_combo.config(values=audio_quality_list)
        quality_combo.set(audio_quality_list[0])

ttk.Radiobutton(format_frame, text="MP4", variable=format_var, value="mp4", command=update_quality_options, style="My.TRadiobutton").pack(side=tk.LEFT, padx=8)
ttk.Radiobutton(format_frame, text="MP3", variable=format_var, value="mp3", command=update_quality_options, style="My.TRadiobutton").pack(side=tk.LEFT, padx=8)

# --- 進捗バー & ステータス ---
progress_var = tk.DoubleVar(value=0.0)
progress_bar = ttk.Progressbar(main_frame, variable=progress_var, maximum=100)
progress_bar.pack(fill=tk.X, pady=(6,2))
status_var = tk.StringVar(value="準備完了")
status_label = ttk.Label(main_frame, textvariable=status_var, font=LABEL_FONT)
status_label.pack(anchor="w")

# --- ダウンロードボタン ---
download_btn = ttk.Button(main_frame, text="ダウンロード", style="My.TButton")
download_btn.pack(pady=6)

# --- ログ表示 ---
ttk.Label(main_frame, text="ログ", font=LABEL_FONT).pack(anchor="w")
log_text = tk.Text(main_frame, height=12, font=ENTRY_FONT)
log_text.pack(fill=tk.BOTH, expand=True, pady=(2,4))

# --- stdout/stderr redirect ---
class StdoutRedirect:
    def __init__(self, text_widget): self.text_widget = text_widget
    def write(self, message):
        if message and message.strip(): safe_insert_log(self.text_widget, message.rstrip())
    def flush(self): pass
sys.stdout = StdoutRedirect(log_text)
sys.stderr = StdoutRedirect(log_text)

# --- ダウンロード処理 ---
def download_worker():
    txt = url_text.get("1.0", tk.END).strip()
    if not txt:
        messagebox.showerror("Error", "URLを入力してください")
        return

    folder = folder_var.get().strip()
    if not folder or not os.path.isdir(folder):
        messagebox.showerror("Error", "保存先フォルダを選択してください")
        return

    urls = [u.split("&list=")[0].strip() for u in txt.splitlines() if u.strip()]
    total_videos = len(urls)
    if total_videos == 0:
        messagebox.showerror("Error", "有効なURLがありません")
        return

    ffmpeg_path = get_ffmpeg_path()
    if format_var.get() == "mp3" and ffmpeg_path is None:
        messagebox.showerror("Error", "MP3 には ffmpeg が必要です")
        return

    current_index = [0]

    def progress_hook(d):
        status = d.get("status")
        if status == "downloading":
            try:
                percent = float(d.get("_percent_str","0.0").replace("%",""))
                overall = ((current_index[0]-1)+percent/100)/total_videos*100
                progress_var.set(overall)
                status_var.set(f"{current_index[0]}/{total_videos} {percent:.1f}%  ETA: {d.get('_eta_str','?')}")
            except: pass
        elif status == "finished":
            safe_insert_log(log_text, f"=== {d.get('filename','完了')} 完了 ===")
            progress_var.set(current_index[0]/total_videos*100)

    selected_quality = quality_var.get().split()[0]
    ydl_opts_base = {
        'outtmpl': os.path.join(folder, '%(title)s.%(ext)s'),
        'logger': LoggerRedirect(log_text),
        'progress_hooks':[progress_hook],
        'noplaylist': True,
        'quiet': True,
        'ffmpeg_location': ffmpeg_path  # ← トップレベルで指定
    }

    if format_var.get() == "mp3":
        ydl_opts_base.update({
            'format': selected_quality or 'bestaudio/best',
            'postprocessors':[{
                'key':'FFmpegExtractAudio',
                'preferredcodec':'mp3',
                'preferredquality':'192',
            }]
        })
    else:
        ydl_opts_base.update({
            'format': selected_quality or 'bestvideo+bestaudio/best',
            'merge_output_format':'mp4'
        })

    def run():
        download_btn.config(state=tk.DISABLED)
        progress_var.set(0)
        try:
            for idx, u in enumerate(urls, start=1):
                current_index[0] = idx
                safe_insert_log(log_text, f"[{idx}/{total_videos}] {u}")
                with YoutubeDL(ydl_opts_base) as ydl:
                    ydl.download([u])
            status_var.set("すべて完了")
            progress_var.set(100.0)
            safe_insert_log(log_text, "=== 全ダウンロード完了 ===")
        except Exception as e:
            safe_insert_log(log_text, f"致命的エラー: {e}")
            safe_insert_log(log_text, traceback.format_exc())
            status_var.set("エラー発生")
        finally:
            download_btn.config(state=tk.NORMAL)
            progress_var.set(0.0)

    threading.Thread(target=run, daemon=True).start()

download_btn.config(command=download_worker)
update_quality_options()
app.mainloop()
