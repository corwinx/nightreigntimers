import time
import tkinter as tk
from tkinter import ttk
import keyboard
import logging
import math

minute = 60
dbgflag = False  # Set to True for debugging mode
if dbgflag:
    minute = 3 # Debugging mode: speed up to x seconds per minute
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# 8 phases: [Safe, Closing, Safe, Closing] x 2 days
PHASE_DURATIONS = [
    4.5 * minute, 3 * minute,  # Day 1, First Storm Safe/Closing
    3.5 * minute, 3 * minute,  # Day 1, Second Storm Safe/Closing
    4.5 * minute, 3 * minute,  # Day 2, First Storm Safe/Closing
    3.5 * minute, 3 * minute,  # Day 2, Second Storm Safe/Closing
]
PHASE_LABELS = [
    "First Storm Safe",
    "First Storm Closing",
    "Second Storm Safe",
    "Second Storm Closing",
    "First Storm Safe",
    "First Storm Closing",
    "Second Storm Safe",
    "Second Storm Closing",
]
SECTION_TITLES = {
    0: "Day 1",
    4: "Day 2"
}
BOSS_PAUSE_AFTER = 3  # Pause after phase 3 (Day 1, Second Storm Closing)
BEEP_WARNING_SECONDS = 5 # Tones when 5 seconds left before a closing phase

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

class NIGHTREIGNTimers:
    def __init__(self, window):
        self.window = window
        self.phase = 0
        self.running = False
        self.paused_for_boss = False
        self.start_time = None
        self.phase_start_time = None
        self.progress = []
        self.labels = []
        self.setup_gui()
        self.window.after(200, self.update_instruction)

    def setup_gui(self):
        self.window.title("Corwin's Vibecode NIGHTREIGN Timers")
        self.window.configure(bg='#000000')
        self.window.resizable(False, False)

        style = ttk.Style(self.window)
        style.theme_use('default')
        style.configure('Green.Horizontal.TProgressbar', troughcolor="#000000", background='#00aa00')
        style.configure('Red.Horizontal.TProgressbar', troughcolor='#000000', background='#ff0000')
        style.configure('Default.Horizontal.TProgressbar', troughcolor='#000000', background='#808080')

        frame = tk.Frame(self.window, bg='#000000')
        frame.pack(padx=20, pady=20, anchor='nw')

        row = 1
        self.labels = []
        self.progress = []
        labeltitle = tk.Label(frame, text="NIGHTREIGN Timers", font=("Helvetica", 16, "bold"), bg='#000000', fg='#ffffff')
        labeltitle.grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky='w')
        for i, label in enumerate(PHASE_LABELS):
            # Insert section title if needed
            if i in SECTION_TITLES:
                section = tk.Label(frame, text=SECTION_TITLES[i], font=("Helvetica", 13, "bold"), bg='#000000', fg='#447efb')
                section.grid(row=row, column=0, columnspan=2, sticky='w', pady=(10,2))
                row += 1
            lbl = tk.Label(frame, text=label, font=("Helvetica", 10), bg='#000000', fg='#cccccc', width=18, anchor='w')
            lbl.grid(row=row, column=0, sticky='w', padx=(0, 2), pady=1)
            bar = ttk.Progressbar(frame, length=200, mode='determinate', maximum=PHASE_DURATIONS[i], style='Green.Horizontal.TProgressbar')
            bar.grid(row=row, column=1, sticky='w', pady=1)
            self.labels.append(lbl)
            self.progress.append(bar)
            row += 1

        self.phase_time_label = tk.Label(
            frame,
            text="00:00 / 00:00",
            font=("Helvetica", 13, "bold"),
            bg='#000000',
            fg="#00bfff"
        )
        self.phase_time_label.grid(row=row, column=0, columnspan=2, pady=(10, 0), sticky='w')
        row += 1

        self.instruction = tk.Label(
            frame,
            text="Press [F8] to start/reset timer",
            font=("Helvetica", 13),
            bg='#000000',
            fg='#ffffff',
            wraplength=600,
            justify="left"
        )
        self.instruction.grid(row=row, column=0, columnspan=2, pady=(10, 15), sticky='w')

        keyboard.add_hotkey('f8', self.on_hotkey)

        # --- Info Panel (right side) ---
        info_frame = tk.Frame(self.window, bg='#222222', bd=2, relief='groove')
        info_frame.place(x=400, y=20, width=220, height=425)

        info_title = tk.Label(info_frame, text="Leveling Rune Cost", font=("Helvetica", 12, "bold"), bg='#222222', fg="#447efb")
        info_title.grid(row=0, column=0, columnspan=3, pady=(5, 2))

        headers = ["Level", "Level Cost", "Total Spent"]
        for col, text in enumerate(headers):
            tk.Label(info_frame, text=text, font=("Helvetica", 10, "bold"), bg='#222222', fg='#cccccc').grid(row=1, column=col, padx=4, pady=2, sticky='w')

        # Level and cost data
        level_costs = [
            ("1", 0),
            ("2", 3698),
            ("3", 7922),
            ("4", 12348),
            ("5", 16978),
            ("6", 21818),
            ("7", 26869),
            ("8", 32137),
            ("9", 37624),
            ("10", 43335),
            ("11", 49271),
            ("12", 55439),
            ("13", 61840),
            ("14", 68479),
            ("15", 75358),
        ]
        running_total = 0
        for row_idx, (level, cost) in enumerate(level_costs, start=2):
            running_total += cost
            tk.Label(info_frame, text=level, bg='#222222', fg='#ffffff', font=("Helvetica", 10)).grid(row=row_idx, column=0, padx=4, pady=1, sticky='w')
            tk.Label(info_frame, text=str(cost), bg='#222222', fg='#ffffff', font=("Helvetica", 10)).grid(row=row_idx, column=1, padx=4, pady=1, sticky='w')
            tk.Label(info_frame, text=str(running_total), bg='#222222', fg='#ffffff', font=("Helvetica", 10)).grid(row=row_idx, column=2, padx=4, pady=1, sticky='w')

        # Adjust window size and progress bar frame position to fit new layout
        self.window.geometry("640x465")
        frame.place(x=20, y=20) 

    def on_hotkey(self):
        window.attributes('-topmost', True)  # Push the window to the top
        window.update
        window.attributes('-topmost', False)  # Don't keep forcing always on top
        if self.paused_for_boss:
            self.paused_for_boss = False
            self.phase += 1
            self.phase_start_time = time.time()
            self.running = True
            self.instruction.config(text="")
            self.window.after(100, self.run_phase)
        else:
            self.reset_all()
            self.running = True
            self.phase = 0
            self.start_time = time.time()
            self.phase_start_time = self.start_time
            self.instruction.config(text="")
            self.window.after(100, self.run_phase)

    def reset_all(self):
        self.running = False
        self.paused_for_boss = False
        for i, bar in enumerate(self.progress):
            bar.config(value=0, style='Green.Horizontal.TProgressbar')
            self.labels[i].config(bg='#000000', fg='#cccccc')
        self.instruction.config(text="Press [F8] to start/reset timer")

    def beep_notice(self):
        if HAS_WINSOUND:
            winsound.Beep(130, 400)
            winsound.Beep(110, 300)
            winsound.Beep(98, 500)            
        else:
            self.window.bell()

    def update_instruction(self):
        if self.paused_for_boss:
            self.instruction.config(text="Boss fight! Press [F8] when ready to resume.", fg='#447efb')
        elif not self.running:
            self.instruction.config(text="Press [F8] to start/reset timer", fg='#ffffff')
        else:
            self.instruction.config(text="", fg='#ffffff')
        self.window.after(200, self.update_instruction)

    def run_phase(self):
        if not self.running or self.phase >= len(PHASE_DURATIONS):
            self.running = False
            self.instruction.config(text="Press [F8] to start/reset timer", fg='#ffffff')
            self.phase_time_label.config(text="00:00 / 00:00")
            return

        # Highlight current phase
        for i, lbl in enumerate(self.labels):
            if i == self.phase:
                lbl.config(bg='#00aa00' if self.phase % 2 == 0 else '#ff0000', fg='#ffffff')
            else:
                lbl.config(bg='#000000', fg='#cccccc')
        bar = self.progress[self.phase]
        bar.config(style='Green.Horizontal.TProgressbar' if self.phase % 2 == 0 else 'Red.Horizontal.TProgressbar')

        duration = PHASE_DURATIONS[self.phase]
        elapsed = time.time() - self.phase_start_time
        remaining = duration - elapsed
        #logging.debug(f"Phase {self.phase + 1}: Elapsed: {elapsed:.2f}s, Remaining: {remaining:.2f}s")
        bar['value'] = elapsed

        # Update phase time label
        def format_time(secs):
            mins = int(secs) // 60
            s = int(secs) % 60
            return f"{mins:02}:{s:02}"

        self.phase_time_label.config(
            text=f"{format_time(elapsed)} / {format_time(duration)} ({math.ceil(remaining)} seconds remaining)"
        )

        # Beep warning
        if 0 < remaining < BEEP_WARNING_SECONDS and abs(bar['value'] - (duration - BEEP_WARNING_SECONDS)) < 0.3 and self.phase % 2 == 0:
            self.beep_notice()

        if elapsed >= duration:
            bar['value'] = duration
            bar.config(style='Default.Horizontal.TProgressbar')
            self.labels[self.phase].config(bg='#808080', fg='#ffffff')
            self.phase_time_label.config(text=f"{format_time(duration)} / {format_time(duration)}")
            if self.phase == BOSS_PAUSE_AFTER:
                self.paused_for_boss = True
                self.running = False
                self.instruction.config(text="Boss fight! Press [F8] when ready to resume.", fg='#447efb')
                return
            self.phase += 1
            if self.phase < len(PHASE_DURATIONS):
                self.phase_start_time = time.time()
                self.window.after(100, self.run_phase)
            else:
                self.running = False
                self.instruction.config(text="Press [F8] to start/reset timer", fg='#ffffff')
                self.phase_time_label.config(text="00:00 / 00:00")
            return

        self.window.after(200, self.run_phase)

def main():
    global window 
    window = tk.Tk()
    app = NIGHTREIGNTimers(window)
    window.mainloop()

if __name__ == "__main__":
    main()
