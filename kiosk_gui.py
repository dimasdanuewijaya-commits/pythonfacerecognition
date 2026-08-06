import tkinter as tk
from tkinter import font as tkFont
from tkinter import messagebox
import time
from datetime import datetime
import cv2
from PIL import Image, ImageTk
from attendance_taker import FaceRecognizerService

# Konstanta Nilai Mutu
MUTU_RATES = {
    "stand by": 1.0,
    "piket": 2.0,
    "teaching": 3.0,
    "rapat": 2.5,
    "riset": 3.5
}
RUPIAH_PER_MUTU = 7500

class KioskGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Lab Attendance Kiosk")
        self.geometry("800x480")  # Ukuran umum LCD Raspberry Pi (7 inch)
        self.configure(bg="white")
        
        # Font definitions
        self.title_font = tkFont.Font(family='Helvetica', size=24, weight='bold')
        self.header_font = tkFont.Font(family='Helvetica', size=18, weight='bold')
        self.normal_font = tkFont.Font(family='Helvetica', size=16)
        
        # Variables to track state
        self.current_user = None
        self.attendance_type = None # "datang" or "pulang"
        self.recognizer = None
        
        # Load AI models in background to avoid freezing the startup UI
        import threading
        threading.Thread(target=self._load_recognizer, daemon=True).start()
        
        # Container for all frames
        self.container = tk.Frame(self, bg="white")
        self.container.pack(side="top", fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)
        
        self.frames = {}
        for F in (MainScreen, VerifyIDScreen, FaceIDScreen, RFIDScreen, ShiftMutuScreen, SuccessScreen):
            page_name = F.__name__
            frame = F(parent=self.container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")
            
        self.show_frame("MainScreen")
        
    def _load_recognizer(self):
        self.recognizer = FaceRecognizerService(detect_every=3)

    def show_frame(self, page_name):
        frame = self.frames[page_name]
        frame.tkraise()
        if hasattr(frame, 'on_show'):
            frame.on_show()

class MainScreen(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="white")
        self.controller = controller
        
        header_frame = tk.Frame(self, bg="white")
        header_frame.pack(pady=10, fill=tk.X)
        
        # Place logo on the left (or centered)
        try:
            logo_img = Image.open("logo.jpeg")
            logo_img.thumbnail((80, 80))
            self.logo_photo = ImageTk.PhotoImage(logo_img)
            tk.Label(header_frame, image=self.logo_photo, bg="white").pack(pady=10)
        except Exception as e:
            pass
        
        # Clock
        self.time_label = tk.Label(self, text="", font=self.controller.title_font, bg="white", fg="#333333")
        self.time_label.pack(pady=20)
        self.update_clock()
        
        from tkmacosx import Button as MacButton
        
        # Buttons
        btn_frame = tk.Frame(self, bg="white")
        btn_frame.pack(pady=50)
        
        MacButton(btn_frame, text="Absen Datang", font=self.controller.normal_font, 
                  bg="#007bff", fg="white", borderless=1,
                  padx=30, pady=20, cursor="hand2",
                  command=lambda: self.select_type("datang")).pack(side=tk.LEFT, padx=20)
                  
        MacButton(btn_frame, text="Absen Pulang", font=self.controller.normal_font, 
                  bg="#007bff", fg="white", borderless=1,
                  padx=30, pady=20, cursor="hand2",
                  command=lambda: self.select_type("pulang")).pack(side=tk.LEFT, padx=20)

    def select_type(self, att_type):
        self.controller.attendance_type = att_type
        self.controller.show_frame("VerifyIDScreen")
        
    def update_clock(self):
        now = datetime.now().strftime("%A, %d %B %Y \n\n %H:%M:%S")
        self.time_label.config(text=now)
        self.after(1000, self.update_clock)

class VerifyIDScreen(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="white")
        self.controller = controller
        
        tk.Label(self, text="Verified Your ID", font=self.controller.title_font, bg="white", fg="#007bff").pack(pady=50)
        
        from tkmacosx import Button as MacButton
        
        btn_frame = tk.Frame(self, bg="white")
        btn_frame.pack(pady=20)
        
        MacButton(btn_frame, text="Face ID", font=self.controller.normal_font, 
                  bg="#007bff", fg="white", borderless=1,
                  padx=50, pady=15, cursor="hand2", 
                  command=lambda: self.controller.show_frame("FaceIDScreen")).pack(pady=10)
        MacButton(btn_frame, text="RFID", font=self.controller.normal_font, 
                  bg="#007bff", fg="white", borderless=1,
                  padx=50, pady=15, cursor="hand2", 
                  command=lambda: self.controller.show_frame("RFIDScreen")).pack(pady=10)
                  
        MacButton(self, text="< Back", font=self.controller.normal_font, 
                  bg="#cccccc", fg="black", borderless=1, padx=20, pady=10,
                  command=lambda: self.controller.show_frame("MainScreen")).pack(side=tk.BOTTOM, pady=20, anchor=tk.W, padx=20)

class FaceIDScreen(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="white")
        self.controller = controller
        self.cap = None
        
        tk.Label(self, text="Scan Your Face", font=self.controller.title_font, bg="white", fg="#007bff").pack(pady=10)
        
        self.video_label = tk.Label(self, bg="white")
        self.video_label.pack(pady=10)
        
        self.status_label = tk.Label(self, text="", font=self.controller.normal_font, bg="white", fg="red")
        self.status_label.pack(pady=5)
                  
        from tkmacosx import Button as MacButton
        MacButton(self, text="< Back", font=self.controller.normal_font, 
                  bg="#cccccc", fg="black", borderless=1, padx=20, pady=10,
                  command=self.go_back).pack(side=tk.BOTTOM, pady=20, anchor=tk.W, padx=20)
                  
    def on_show(self):
        self.status_label.config(text="Memuat Kamera...", fg="#007bff")
        self.update() # Force UI to draw before blocking
        # Open camera when screen is shown, delayed slightly to let UI switch
        self.after(50, self._start_camera)
        
    def _start_camera(self):
        if self.cap is None:
            self.cap = cv2.VideoCapture(0)
            # Flush the macOS camera buffer of old frames
            for _ in range(5):
                self.cap.read()
        self.camera_ready_time = time.time() + 1.5 # 1.5 second warmup
        self.is_processing = False
        self.update_frame()
        
    def update_frame(self):
        if self.controller.recognizer is None:
            self.status_label.config(text="Memuat AI Model...", fg="#007bff")
            self.video_loop = self.after(100, self.update_frame)
            return

        if self.cap is not None and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.flip(frame, 1)
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Run recognition
                results = self.controller.recognizer.process_frame(frame_rgb)
                
                # Draw boxes and check for success
                recognized_name = None
                for res in results:
                    left, top, right, bottom = res['box']
                    name = res['name']
                    color = (0, 255, 0) if name != "unknown" else (255, 0, 0)
                    cv2.rectangle(frame_rgb, (left, top), (right, bottom), color, 2)
                    cv2.putText(frame_rgb, name, (left, top-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                    
                    if name != "unknown":
                        recognized_name = name
                
                img = Image.fromarray(frame_rgb).resize((480, 360))
                imgtk = ImageTk.PhotoImage(image=img)
                self.video_label.imgtk = imgtk
                self.video_label.configure(image=imgtk)
                
                if getattr(self, 'is_processing', False):
                    return
                
                if recognized_name and time.time() > getattr(self, 'camera_ready_time', 0):
                    self.is_processing = True
                    self.status_label.config(text=f"Welcome {recognized_name}!", fg="green")
                    self.after(1000, lambda n=recognized_name: self.process_success(n))
                    return # Stop looping
                else:
                    if results:
                        self.status_label.config(text="Wajah tidak dikenal", fg="red")
                    else:
                        self.status_label.config(text="")
                        
            self.video_loop = self.after(30, self.update_frame)

    def stop_camera(self):
        if hasattr(self, 'video_loop'):
            self.after_cancel(self.video_loop)
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def go_back(self):
        self.stop_camera()
        self.controller.show_frame("VerifyIDScreen")
        
    def process_success(self, name):
        self.stop_camera()
        self.controller.current_user = name
        
        # Log to DB
        success, msg = self.controller.recognizer.record_attendance(name, method="face_id")
        if not success:
            print(f"DB Log Failed: {msg}")
            
        if self.controller.attendance_type == "datang":
            self.controller.show_frame("SuccessScreen")
        else:
            self.controller.show_frame("ShiftMutuScreen")

class RFIDScreen(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="white")
        self.controller = controller
        
        tk.Label(self, text="Tempel Kartu Asisten Anda", font=self.controller.title_font, bg="white", fg="#007bff").pack(pady=50)
        
        # Simulating RFID tap for testing on laptop
        self.rfid_entry = tk.Entry(self, font=self.controller.normal_font)
        self.rfid_entry.pack(pady=20)
        
        from tkmacosx import Button as MacButton
        MacButton(self, text="[Simulasi Tap Kartu]", bg="green", fg="white", borderless=1, padx=20, pady=10,
                  command=self.simulate_success).pack(pady=5)
                  
        MacButton(self, text="< Back", font=self.controller.normal_font, 
                  bg="#cccccc", fg="black", borderless=1, padx=20, pady=10,
                  command=lambda: self.controller.show_frame("VerifyIDScreen")).pack(side=tk.BOTTOM, pady=20, anchor=tk.W, padx=20)

    def on_show(self):
        self.rfid_entry.delete(0, tk.END)
        self.rfid_entry.focus()
        
    def simulate_success(self):
        self.controller.current_user = "Dimas (Asisten)"
        if self.controller.attendance_type == "datang":
            self.controller.show_frame("SuccessScreen")
        else:
            self.controller.show_frame("ShiftMutuScreen")

class ShiftMutuScreen(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="white")
        self.controller = controller
        
        self.title_label = tk.Label(self, text="Pilih Shift & Mutu", font=self.controller.title_font, bg="white", fg="black")
        self.title_label.pack(pady=5)
        
        # Legend
        legend_text = "1: Standby | 2: Piket | 3: Teaching | 4: Rapat | 5: Riset"
        tk.Label(self, text=legend_text, font=self.controller.normal_font, bg="white", fg="gray").pack(pady=5)
        
        self.selected_mutu_per_shift = {r: None for r in range(5)}
        self.buttons = []
        
        grid_frame = tk.Frame(self, bg="white")
        grid_frame.pack(pady=10)
        
        from tkmacosx import Button as MacButton
        
        shifts = ["shift 1", "shift 2", "shift 3", "shift 4", "shift 5"]
        mutu_keys = ["stand by", "piket", "teaching", "rapat", "riset"]
        
        for r, shift in enumerate(shifts):
            tk.Label(grid_frame, text=shift, font=self.controller.normal_font, bg="white", fg="#007bff").grid(row=r, column=0, padx=20, pady=5, sticky=tk.E)
            
            row_buttons = []
            for c, mutu in enumerate(mutu_keys):
                btn = MacButton(grid_frame, text=str(c+1), font=self.controller.normal_font, 
                                bg="white", fg="#007bff", borderless=1, padx=20, pady=5,
                                command=lambda s=shift, m=mutu, r=r, c=c: self.select_cell(s, m, r, c))
                btn.grid(row=r, column=c+1, padx=5, pady=5)
                row_buttons.append(btn)
            self.buttons.append(row_buttons)
            
        self.confirm_btn = MacButton(self, text="confirm", font=self.controller.normal_font, 
                                     bg="#cccccc", fg="black", borderless=1, padx=40, pady=10,
                                     command=self.submit)
        self.confirm_btn.pack(pady=10)
        
        MacButton(self, text="< Back", font=self.controller.normal_font, 
                  bg="#cccccc", fg="black", borderless=1, padx=20, pady=10,
                  command=lambda: self.controller.show_frame("VerifyIDScreen")).pack(side=tk.BOTTOM, pady=10, anchor=tk.W, padx=20)
                  
    def select_cell(self, shift, mutu, r, c):
        # Toggle logic: if clicking the already selected mutu, unselect it
        if self.selected_mutu_per_shift[r] == mutu:
            self.selected_mutu_per_shift[r] = None
        else:
            self.selected_mutu_per_shift[r] = mutu
            
        mutu_keys = ["stand by", "piket", "teaching", "rapat", "riset"]
            
        # Update colors for this specific row
        for i, btn in enumerate(self.buttons[r]):
            if self.selected_mutu_per_shift[r] == mutu_keys[i]:
                btn.configure(bg="#007bff", fg="white")
            else:
                btn.configure(bg="white", fg="#007bff")
                
        # Enable confirm button if AT LEAST ONE shift is selected
        if any(m is not None for m in self.selected_mutu_per_shift.values()):
            self.confirm_btn.configure(bg="green", fg="white", text="confirm")
        else:
            self.confirm_btn.configure(bg="#cccccc", fg="black", text="confirm")
        
    def submit(self):
        selected_mutus = [m for m in self.selected_mutu_per_shift.values() if m is not None]
        if not selected_mutus:
            self.confirm_btn.configure(text="Pilih minimal 1!", bg="red")
            self.after(1000, lambda: self.confirm_btn.configure(text="confirm", bg="#cccccc"))
            return
            
        total_mutu_value = sum(MUTU_RATES[m] for m in selected_mutus)
        self.controller.total_rp = int(total_mutu_value * RUPIAH_PER_MUTU)
        self.controller.show_frame("SuccessScreen")
        
    def on_show(self):
        user = self.controller.current_user
        self.title_label.config(text=f"Halo, {user}!\nPilih Shift & Mutu")
        self.selected_mutu_per_shift = {r: None for r in range(5)}
        for row in self.buttons:
            for btn in row:
                btn.configure(bg="white", fg="#007bff")
        self.confirm_btn.configure(bg="#cccccc", fg="black", text="confirm")

class SuccessScreen(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="white")
        self.controller = controller
        self.msg_label = tk.Label(self, text="", font=self.controller.title_font, bg="white", fg="#007bff", justify=tk.CENTER)
        self.msg_label.pack(expand=True)
        
    def on_show(self):
        user = self.controller.current_user
        if self.controller.attendance_type == "datang":
            msg = f"Have a great day,\n{user}!"
        else:
            rp = getattr(self.controller, 'total_rp', 0)
            msg = f"You did so well today.\nGet home safe, okay?\n\nTotal Mutu Hari Ini: Rp {rp:,}"
            
        self.msg_label.config(text=msg)
        
        # Auto redirect back to main screen after 4 seconds
        self.after(4000, lambda: self.controller.show_frame("MainScreen"))

if __name__ == "__main__":
    app = KioskGUI()
    app.mainloop()
