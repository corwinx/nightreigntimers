import time
import tkinter as tk
from tkinter import ttk
import threading
import psutil
import pygetwindow as gw
import pystray
from PIL import Image, ImageDraw

minute = 60
dbgflag = False  # Set to True for debugging mode
if dbgflag:
    minute = 3  # Debugging mode: speed up to x seconds per minute

# 8 phases: [Safe, Closing, Safe, Closing] x 2 days
PHASE_DURATIONS = [
    4.5 * minute, 3 * minute,  # Day 1, First Storm Safe/Closing
    3.5 * minute, 3 * minute,  # Day 1, Second Storm Safe/Closing
    4.5 * minute, 3 * minute,  # Day 2, First Storm Safe/Closing
    3.5 * minute, 3 * minute,  # Day 2, Second Storm Safe/Closing
]
PHASE_LABELS = [
    "Day 1: First Storm Safe",
    "Day 1: First Storm Closing",
    "Day 1: Second Storm Safe",
    "Day 1: Second Storm Closing",
    "Day 2: First Storm Safe",
    "Day 2: First Storm Closing",
    "Day 2: Second Storm Safe",
    "Day 2: Second Storm Closing",
]
BOSS_PAUSE_AFTER = 3  # Pause after phase 3 (Day 1, Second Storm Closing)
BEEP_WARNING_SECONDS = 5

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

class OverlayTimers:
    def __init__(self, window):
        self.window = window
        self.phase = 0
        self.running = False
        self.paused_for_boss = False
        self.start_time = None
        self.phase_start_time = None
        self.total_duration = sum(PHASE_DURATIONS)
        self.total_elapsed = 0
        self.tray_icon = None
        self._setup_overlay()
        self._setup_gui()
        self.window.after(200, self.update_ui)
        self.check_game_focus()  # Start periodic check
        threading.Thread(target=self.setup_tray, daemon=True).start()

    def _setup_overlay(self):
        # Make the window borderless, always on top, and transparent background
        self.window.overrideredirect(True) # also hides from taskbar
        self.window.attributes('-topmost', True)
        self.window.attributes('-alpha', 0.70)  # Slight transparency
        self.window.configure(bg='#222222')
        # Place overlay at top center of the screen
        screen_width = self.window.winfo_screenwidth()
        self.window.geometry(f"420x110+{screen_width//2-210}+5")

    def _setup_gui(self):
        style = ttk.Style(self.window)
        style.theme_use('default')
        style.configure('Current.Horizontal.TProgressbar', troughcolor="#222222", background='#00aa00', thickness=16)
        style.configure('Red.Horizontal.TProgressbar', troughcolor="#222222", background='#ff2222', thickness=16)
        style.configure('Flash.Horizontal.TProgressbar', troughcolor="#222222", background='#992222', thickness=16)
        style.configure('Total.Horizontal.TProgressbar', troughcolor="#222222", background='#447efb', thickness=10)

        # --- [x] Close Button ---
        close_btn = tk.Label(self.window, text="[x]", font=("Segoe UI", 11, "bold"), bg="#222222", fg="#ff6666", cursor="hand2")
        close_btn.place(relx=1.0, x=-8, y=2, anchor="ne")
        close_btn.bind("<Button-1>", lambda e: self.window.destroy())

        # Use place instead of pack for the main frame to avoid covering the [x] button
        frame = tk.Frame(self.window, bg='#222222')
        frame.place(x=0, y=0, relwidth=1, relheight=1, anchor='nw')

        # Phase label and [x] close button on the same row
        phase_row = tk.Frame(frame, bg='#222222')
        phase_row.pack(fill='x', pady=(0, 0))

        self.phase_label = tk.Label(phase_row, text="[Phase]", font=("Segoe UI", 13, "bold"), bg='#222222', fg='#ffffff')
        self.phase_label.pack(side='left', anchor='w')

        close_btn = tk.Label(phase_row, text="[x]", font=("Segoe UI", 11, "bold"), bg="#222222", fg="#ff6666", cursor="hand2")
        close_btn.pack(side='right', anchor='e', padx=(0, 2))
        close_btn.bind("<Button-1>", lambda e: self.window.destroy())

        # Current phase progress bar
        self.phase_bar = ttk.Progressbar(frame, length=380, mode='determinate', maximum=1, style='Current.Horizontal.TProgressbar')
        self.phase_bar.pack(pady=(4, 8))

        # Total progress bar
        self.total_bar = ttk.Progressbar(frame, length=380, mode='determinate', maximum=1, style='Total.Horizontal.TProgressbar')
        self.total_bar.pack(pady=(0, 0))

        # Combined time/instruction label
        self.status_label = tk.Label(frame, text="Press [F8] to start/reset timer", font=("Segoe UI", 11), bg='#222222', fg='#ffffcc', wraplength=400, justify="left")
        self.status_label.pack(anchor='w', pady=(8, 0))

        # Hotkey
        import keyboard
        keyboard.add_hotkey('f8', self.on_hotkey)

    def on_hotkey(self):
        self.window.attributes('-topmost', True)
        self.window.update()
        if self.paused_for_boss:
            self.paused_for_boss = False
            self.phase += 1
            self.phase_start_time = time.time()
            self.running = True
            self.status_label.config(text="")
            threading.Thread(target=self.run_timer, daemon=True).start()
        else:
            self.reset_all()
            self.running = True
            self.phase = 0
            self.start_time = time.time()
            self.phase_start_time = self.start_time
            self.total_elapsed = 0
            self.status_label.config(text="")
            threading.Thread(target=self.run_timer, daemon=True).start()

    def reset_all(self):
        self.running = False
        self.paused_for_boss = False
        self.phase = 0
        self.total_elapsed = 0
        self.phase_bar.config(value=0, maximum=1)
        self.total_bar.config(value=0, maximum=1)
        self.phase_label.config(text="Phase")
        self.status_label.config(text="Press [F8] to start/reset timer", fg='#cccccc')

    def beep_notice(self):
        def do_beep():
            if HAS_WINSOUND:
                winsound.Beep(130, 400)
                winsound.Beep(110, 300)
                winsound.Beep(98, 500)
            else:
                self.window.bell()
        threading.Thread(target=do_beep, daemon=True).start()

    def update_ui(self):
        # Called every 200ms to update the overlay UI
        if self.running and self.phase < len(PHASE_DURATIONS):
            duration = PHASE_DURATIONS[self.phase]
            elapsed = time.time() - self.phase_start_time
            total_elapsed = (self.total_elapsed + elapsed)
            remaining = max(0, duration - elapsed)
            # Update progress bars
            self.phase_bar.config(maximum=duration, value=min(elapsed, duration))
            self.total_bar.config(maximum=self.total_duration, value=min(total_elapsed, self.total_duration))
            # Update labels
            self.phase_label.config(text=f"{PHASE_LABELS[self.phase]} ({self._format_time(duration)})")
            self.status_label.config(
                text=f"{self._format_time(remaining)} remaining"
            )
            # Change color: green for safe, flashing red for closing
            if self.phase % 2 == 0:
                self.phase_bar.config(style='Current.Horizontal.TProgressbar')
            else:
                if hasattr(self, '_flash') and self._flash:
                    self.phase_bar.config(style='Flash.Horizontal.TProgressbar')
                else:
                    self.phase_bar.config(style='Red.Horizontal.TProgressbar')
                self._flash = not getattr(self, '_flash', False)
        else:
            # Show instructions if not running
            if self.paused_for_boss:
                self.status_label.config(text="Boss fight! Press [F8] when ready to resume.", fg='#447efb')
            else:
                self.status_label.config(text="Press [F8] to start/reset timer", fg='#cccccc')
        self.window.after(200, self.update_ui)

    def run_timer(self):
        while self.running and self.phase < len(PHASE_DURATIONS):
            duration = PHASE_DURATIONS[self.phase]
            elapsed = time.time() - self.phase_start_time
            remaining = duration - elapsed

            # Beep warning
            if 0 < remaining < BEEP_WARNING_SECONDS and abs(elapsed - (duration - BEEP_WARNING_SECONDS)) < 0.3 and self.phase % 2 == 0:
                self.beep_notice()

            if elapsed >= duration:
                self.phase_bar.config(value=duration)
                self.total_elapsed += duration
                if self.phase == BOSS_PAUSE_AFTER:
                    self.paused_for_boss = True
                    self.running = False
                    self.status_label.config(text="Boss fight! Press [F8] when ready to resume.", fg='#447efb')
                    return
                self.phase += 1
                if self.phase < len(PHASE_DURATIONS):
                    self.phase_start_time = time.time()
                continue
            time.sleep(0.1)
        self.running = False
        self.status_label.config(text="Press [F8] to start/reset timer", fg='#cccccc')

    def _format_time(self, secs):
        mins = int(secs) // 60
        s = int(secs) % 60
        return f"{mins:02}:{s:02}"

    def check_game_focus(self):
        # Check if nightreign.exe is running and in focus
        game_running = False
        game_focused = False

        # Check if process is running
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] and proc.info['name'].lower() == 'nightreign.exe':
                game_running = True
                break

        # Check if window is focused
        if game_running:
            try:
                active = gw.getActiveWindow()
                if active and 'nightreign' in active.title.lower():
                    game_focused = True
            except Exception:
                pass

        if game_running and game_focused:
            self.window.deiconify()
            self.window.attributes('-topmost', True)
        else:
            self.window.withdraw()

        # Check again in 1 second
        self.window.after(1000, self.check_game_focus)

    def setup_tray(self):
        # Create a simple icon
        icon_size = 64
        image = Image.new('RGBA', (icon_size, icon_size), (34, 34, 34, 255))
        draw = ImageDraw.Draw(image)
        draw.ellipse((16, 16, 48, 48), fill=(68, 126, 251, 255))  # blue circle
        draw.rectangle((28, 28, 36, 36), fill=(0, 170, 0, 255))   # green square

        menu = pystray.Menu(
            pystray.MenuItem('[Overlay hidden while nightreign.exe not in foreground]', '', enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Exit', self.on_tray_exit)            
        )
        self.tray_icon = pystray.Icon("NightreignTimers", image, "Nightreign Timers Overlay", menu)
        self.tray_icon.run()

    def on_tray_exit(self, icon, item):
        # Clean exit for both tray and app
        if self.tray_icon:
            self.tray_icon.stop()
        self.window.quit()

def main():
    window = tk.Tk()
    app = OverlayTimers(window)
    window.mainloop()

if __name__ == "__main__":
    main()