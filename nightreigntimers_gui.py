import time
import threading
import keyboard
import tkinter as tk
from tkinter import ttk
import sys

# --- Globals for Thread Management ---
timer_thread = None
stop_event = threading.Event()
window = None  # Global reference to the GUI window
minute = 60

dbgflag = False  # Set to True for debugging, False for normal operation
if dbgflag:
    minute = 1 # For debugging, set definition of a minute to lower value

PHASE_1_SAFE_DURATION = 4.5 * minute
RING_1_CLOSING_DURATION = 3 * minute
PHASE_2_SAFE_DURATION = 3.5 * minute
RING_2_CLOSING_DURATION = 3 * minute

TOTAL_DURATION = int(PHASE_1_SAFE_DURATION + RING_1_CLOSING_DURATION + PHASE_2_SAFE_DURATION + RING_2_CLOSING_DURATION)

BEEP_WARNING_SECONDS = 5  # Seconds remaining to trigger beeps/flashes

paused_for_boss = False  # Add this after your other globals
show_boss_pause_message = False

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

def format_time(secs):
    mins = int(secs // 60)
    secs = int(secs % 60)
    return f"{mins:02d}:{secs:02d}"

def start_or_reset_timer():
    global timer_thread, stop_event, paused_for_boss
    global elapsed_timer_thread, elapsed_timer_stop, elapsed_timer_start_time

    if paused_for_boss:
        # Resume from boss pause: DO NOT start a new elapsed timer thread!
        paused_for_boss = False
        global show_boss_pause_message
        show_boss_pause_message = False
        stop_event.clear()
        timer_thread = threading.Thread(target=run_timers, args=(True, elapsed_timer_start_time), daemon=True)
        timer_thread.start()
        return

    # Full reset: stop any previous elapsed timer thread
    if timer_thread and timer_thread.is_alive():
        stop_event.set()
        timer_thread.join()
    stop_event.clear()
    paused_for_boss = False
    window.attributes('-topmost', True)  # Push the window to the top
    window.update
    window.attributes('-topmost', False)  # Don't keep forcing always on top

    # Stop any previous elapsed timer
    if elapsed_timer_thread and elapsed_timer_thread.is_alive():
        elapsed_timer_stop.set()
        elapsed_timer_thread.join()
    elapsed_timer_stop.clear()
    elapsed_timer_start_time = time.time()
    elapsed_timer_thread = threading.Thread(target=run_elapsed_timer, args=(elapsed_timer_start_time,), daemon=True)
    elapsed_timer_thread.start()

    timer_thread = threading.Thread(target=run_timers, args=(False, elapsed_timer_start_time), daemon=True)
    timer_thread.start()

def beep_notice():
    # Louder/longer beep for Windows, fallback to bell otherwise
    def flash_window():
        for _ in range(4):  # Flash 4 times (#ff0000/black/#ff0000/black)
            window.after(0, lambda: [labelring1.config(bg='#ff0000'), labelring2.config(bg='#ff0000')])
            time.sleep(0.15)
            window.after(0, lambda: [labelring1.config(bg='#000000'), labelring2.config(bg='#000000')])
            time.sleep(0.15)
        window.after(0, lambda: [labelring1.config(bg='#000000'), labelring2.config(bg='#000000')])

    if HAS_WINSOUND and sys.platform == "win32":
        # frequency (Hz), duration (ms)
        notes = [130, 110, 98, 130, 92]  # C3, A2, G2, C3, F#2 (tritone)
        durations = [600, 500, 700, 600, 1200]  # Slight variation adds unease

        threading.Thread(target=flash_window, daemon=True).start()
        for freq, dur in zip(notes, durations):
            winsound.Beep(freq, dur)
    else:
        threading.Thread(target=flash_window, daemon=True).start()
        window.bell()

elapsed_timer_thread = None
elapsed_timer_stop = threading.Event()

def run_elapsed_timer(start_time):
    global show_boss_pause_message
    while not elapsed_timer_stop.is_set():
        if show_boss_pause_message:
            window.after(0, lambda: elapsed_label.config(text="Boss fight! Press [F8] when ready to resume."))
        else: 
            elapsed_label.config(bg='#000000', fg='#ffffff', text="Press [F8] to start/reset timer")
        time.sleep(0.2)

def run_timers(resume_from_boss=False, elapsed_timer_start_time=None):
    global paused_for_boss
    # Set all labels to black/#808080 at the start
    if not resume_from_boss:
        window.after(0, lambda: [
            labelring1.config(bg='#000000', fg='#cccccc', text="Phase 1 Safe Duration"),
            labelring2.config(bg='#000000', fg='#cccccc', text="Phase 2 Safe Duration"),
            elapsed_label.config(bg='#000000', fg='#ffffff', text="Press [F8] to start/reset timer"),
            progring1.config(value=0),
            progring2.config(value=0)
        ])
        time.sleep(0.1)
        start_time = elapsed_timer_start_time if elapsed_timer_start_time else time.time()
        elapsed_total = 0
    else:
        # Resuming: skip to Phase 2, keep elapsed time
        start_time = elapsed_timer_start_time if elapsed_timer_start_time else time.time()
        elapsed_total = PHASE_1_SAFE_DURATION + RING_1_CLOSING_DURATION

    # --- Phase 1 Safe Duration ---
    if not resume_from_boss:
        progring1['maximum'] = PHASE_1_SAFE_DURATION
        progring1['value'] = 0
        window.after(0, lambda: labelring1.config(bg='#00aa00', fg='#ffffff'))
        beeped1 = False
        start = time.time()
        while True:
            if stop_event.is_set():
                return
            now = time.time()
            elapsed = now - start
            total_elapsed = now - start_time
            remaining = PHASE_1_SAFE_DURATION - elapsed
            # Beep logic for Safe Duration
            if not beeped1 and remaining < BEEP_WARNING_SECONDS:
                threading.Thread(target=beep_notice, daemon=True).start()
                beeped1 = True
            if elapsed >= PHASE_1_SAFE_DURATION:
                break
            def update():
                progring1['value'] = elapsed
                labelring1.config(text=f"Phase 1 Safe Duration - {format_time(remaining)}")
            window.after(0, update)
            time.sleep(0.2)
        window.after(0, lambda: [
            progring1.config(value=PHASE_1_SAFE_DURATION),
            labelring1.config(text="Phase 1 Safe Duration - 00:00")
        ])
        time.sleep(0.2)
        window.after(0, lambda: labelring1.config(text=f"Phase 1 Ring Closing - {format_time(RING_1_CLOSING_DURATION)}"))

        # --- Phase 1 Ring Closing (flashing) ---
        progring1['maximum'] = RING_1_CLOSING_DURATION
        progring1['value'] = 0
        flash = False
        start = time.time()
        while True:
            if stop_event.is_set():
                return
            now = time.time()
            elapsed = now - start
            total_elapsed = now - start_time
            remaining = RING_1_CLOSING_DURATION - elapsed
            if elapsed >= RING_1_CLOSING_DURATION:
                break
            def update():
                nonlocal flash
                progring1['value'] = elapsed
                flash = not flash
                progring1.config(style='Red.Horizontal.TProgressbar' if flash else 'Default.Horizontal.TProgressbar')
                labelring1.config(bg='#ff0000', fg='#ffffff', text=f"Phase 1 Ring Closing - {format_time(remaining)}")
                #elapsed_label.config(text=f"{format_time(total_elapsed)}")
            window.after(0, update)
            time.sleep(0.2)
        window.after(0, lambda: [
            progring1.config(style='Default.Horizontal.TProgressbar', value=RING_1_CLOSING_DURATION),
            labelring1.config(bg='#808080', fg='#ffffff', text="Phase 1 Ring Completed")
        ])
        time.sleep(0.2)

        # --- PAUSE FOR BOSS ---
        paused_for_boss = True
        global show_boss_pause_message
        show_boss_pause_message = True
        window.after(0, lambda: elapsed_label.config(text="Boss fight! Press [F8] when ready to resume."))
        return  # Exit thread, wait for F8 to resume

    # --- Phase 2 Safe Duration ---
    progring2['maximum'] = PHASE_2_SAFE_DURATION
    progring2['value'] = 0
    window.after(0, lambda: labelring2.config(bg='#00aa00', fg='#ffffff'))
    beeped2 = False
    start = time.time()
    while True:
        if stop_event.is_set():
            return
        now = time.time()
        elapsed = now - start
        total_elapsed = elapsed_total + elapsed
        remaining = PHASE_2_SAFE_DURATION - elapsed
        # Beep logic for Safe Duration
        if not beeped2 and remaining < BEEP_WARNING_SECONDS:
            threading.Thread(target=beep_notice, daemon=True).start()
            beeped2 = True
        if elapsed >= PHASE_2_SAFE_DURATION:
            break
        def update():
            progring2['value'] = elapsed
            labelring2.config(text=f"Phase 2 Safe Duration - {format_time(remaining)}")
            #elapsed_label.config(text=f"{format_time(total_elapsed)}")
        window.after(0, update)
        time.sleep(0.2)
    window.after(0, lambda: [
        progring2.config(value=PHASE_2_SAFE_DURATION),
        labelring2.config(text="Phase 2 Safe Duration - 00:00")
    ])
    time.sleep(0.2)
    window.after(0, lambda: labelring2.config(text=f"Phase 2 Ring Closing - {format_time(RING_2_CLOSING_DURATION)}"))

    # --- Phase 2 Ring Closing (flashing) ---
    progring2['maximum'] = RING_2_CLOSING_DURATION
    progring2['value'] = 0
    flash = False
    start = time.time()
    while True:
        if stop_event.is_set():
            return
        now = time.time()
        elapsed = now - start
        total_elapsed = elapsed_total + PHASE_2_SAFE_DURATION + elapsed
        remaining = RING_2_CLOSING_DURATION - elapsed
        if elapsed >= RING_2_CLOSING_DURATION:
            break
        def update():
            nonlocal flash
            progring2['value'] = elapsed
            flash = not flash
            progring2.config(style='Red.Horizontal.TProgressbar' if flash else 'Default.Horizontal.TProgressbar')
            labelring2.config(bg='#ff0000', fg='#ffffff', text=f"Phase 2 Ring Closing - {format_time(remaining)}")
            #elapsed_label.config(text=f"{format_time(total_elapsed)}")
        window.after(0, update)
        time.sleep(0.2)
    window.after(0, lambda: [
        progring2.config(style='Default.Horizontal.TProgressbar', value=RING_2_CLOSING_DURATION),
        labelring2.config(bg='#808080', fg='#ffffff', text="Phase 2 Ring Completed")
    ])
    time.sleep(0.2)

    # --- End: Show total elapsed time as final value ---
    window.after(0, lambda: elapsed_label.config(text="Press [F8] to start/reset timer"))
    elapsed_timer_stop.set()

def main_gui():
    global window, progring1, progring2
    global labelring1, labelring2, elapsed_label

    window = tk.Tk()
    window.title("Corwin's Vibecode Nightreign Timers")
    window.geometry("610x380")  # Wider window for info panel
    window.configure(bg='#000000')
    window.resizable(False, False)

    # Styles for progress bars
    style = ttk.Style(window)
    style.theme_use('default')
    style.configure('Green.Horizontal.TProgressbar', troughcolor="#000000", background='#00aa00')
    style.configure('Red.Horizontal.TProgressbar', troughcolor='#000000', background='#ff0000')
    style.configure('Default.Horizontal.TProgressbar', troughcolor='#000000', background='#808080')

    # --- Main Timer Panel (left) ---
    timer_frame = tk.Frame(window, bg='#000000')
    
    timer_frame.place(x=0, y=0, width=400, height=360)

    labeltitle = tk.Label(timer_frame, text="Nightreign Timers", font=("Helvetica", 16, "bold"), bg='#000000', fg='#ffffff')
    labeltitle.pack(pady=10, anchor='w', padx=20)

    labelring1 = tk.Label(timer_frame, text="Phase 1 Safe Duration", font=("Helvetica", 14), bg='#000000', fg='#cccccc')
    labelring1.pack(pady=5, anchor='w', padx=20)
    progring1 = ttk.Progressbar(timer_frame, length=300, mode='determinate', maximum=PHASE_1_SAFE_DURATION, style='Green.Horizontal.TProgressbar')
    progring1.pack(pady=5, anchor='w', padx=20)

    labelring2 = tk.Label(timer_frame, text="Phase 2 Safe Duration", font=("Helvetica", 14), bg='#000000', fg='#cccccc')
    labelring2.pack(pady=5, anchor='w', padx=20)
    progring2 = ttk.Progressbar(timer_frame, length=300, mode='determinate', maximum=PHASE_2_SAFE_DURATION, style='Green.Horizontal.TProgressbar')
    progring2.pack(pady=5, anchor='w', padx=20)

    elapsed_label = tk.Label(
        timer_frame,
        text="Press [F8] to start/reset timer",
        font=("Helvetica", 14),
        bg='#000000',
        fg='#ffffff',
        wraplength=340,      # Wrap text at 340 pixels (adjust as needed)
        justify="left"       # Or "center" if you prefer
    )
    elapsed_label.pack(pady=20, anchor='w', padx=20)

    button = tk.Button(timer_frame, text="Exit", command=window.quit)
    button.pack(pady=10, anchor='w', padx=20)

    # --- Info Panel (right) ---
    info_frame = tk.Frame(window, bg='#222222', bd=2, relief='groove')
    info_frame.place(x=345, y=10, width=250, height=350)  # Wider panel, more to the right

    info_title = tk.Label(info_frame, text="Leveling Rune Cost", font=("Helvetica", 12, "bold"), bg='#222222', fg='#ffff66')
    info_title.grid(row=0, column=0, columnspan=3, pady=(5, 2))

    # Table headers
    headers = ["#", "Level Cost", "Total Spend"]
    for col, text in enumerate(headers):
        tk.Label(info_frame, text=text, font=("Helvetica", 10, "bold"), bg='#222222', fg='#cccccc').grid(row=1, column=col, padx=8, pady=2, sticky='w')

    # Table data
    data = [
        ("1", "0", "0"),
        ("2", "3,698", "3,698"),
        ("3", "7,922", "11,620"),
        ("4", "12,348", "23,968"),
        ("5", "16,978", "40,946"),
        ("6", "21,818", "62,764"),
        ("7", "26,869", "89,633"),
        ("8", "32,137", "121,770"),
        ("9", "37,624", "159,394"),
        ("10", "43,335", "202,729"),
        ("11", "49,271", "252,000"),
        ("12", "55,439", "307,439"),
    ]
    for row, (rounded, cost, total) in enumerate(data, start=2):
        tk.Label(info_frame, text=rounded, bg='#222222', fg='#ffffff', font=("Helvetica", 10)).grid(row=row, column=0, padx=8, pady=1, sticky='w')
        tk.Label(info_frame, text=cost, bg='#222222', fg='#ffffff', font=("Helvetica", 10)).grid(row=row, column=1, padx=8, pady=1, sticky='w')
        tk.Label(info_frame, text=total, bg='#222222', fg='#ffffff', font=("Helvetica", 10)).grid(row=row, column=2, padx=8, pady=1, sticky='w')

    # Register F8 hotkey after GUI is initialized
    def on_f8():
        start_or_reset_timer()
    keyboard.add_hotkey('f8', on_f8)

    window.mainloop()

if __name__ == "__main__":
    main_gui()
