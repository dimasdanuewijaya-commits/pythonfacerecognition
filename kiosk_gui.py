import tkinter as tk
from tkinter import font as tkFont
from tkinter import messagebox
import time
from datetime import datetime
import cv2
from PIL import Image, ImageTk
from attendance_taker import FaceRecognizerService
import hardware_manager

# Cross-platform button support (tkmacosx is only for Mac)
try:
    from tkmacosx import Button as MacButton
except ImportError:
    def MacButton(*args, **kwargs):
        kwargs.pop('borderless', None)
        return tk.Button(*args, **kwargs)

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
        
        self.is_fullscreen = True
        self.attributes("-fullscreen", True)
        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Escape>", self.end_fullscreen)
        
        # Font definitions
        self.title_font = tkFont.Font(family='Helvetica', size=32, weight='bold')
        self.header_font = tkFont.Font(family='Helvetica', size=24, weight='bold')
        self.normal_font = tkFont.Font(family='Helvetica', size=18)
        self.large_button_font = tkFont.Font(family='Helvetica', size=22, weight='bold')
        self.huge_time_font = tkFont.Font(family='Helvetica', size=110, weight='bold')
        self.huge_msg_font = tkFont.Font(family='Helvetica', size=48, weight='bold')
        
        # Variables to track state
        self.current_user = None
        self.attendance_type = None # "datang" or "pulang"
        self.recognizer = None
        
        # Hardware Controllers
        self.led = hardware_manager.LEDController()
        self.rfid = hardware_manager.RFIDScanner()
        
        # Load AI models in background to avoid freezing the startup UI
        import threading
        threading.Thread(target=self._load_recognizer, daemon=True).start()
        
        # Container for all frames
        self.container = tk.Frame(self, bg="white")
        self.container.pack(side="top", fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)
        
        self.frames = {}
        for F in (MainScreen, FaceIDScreen, RFIDScreen, ShiftMutuScreen, SuccessScreen, AdminLoginScreen):
            page_name = F.__name__
            frame = F(parent=self.container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")
            
        self.show_frame("MainScreen")
        
    def _load_recognizer(self):
        self.recognizer = FaceRecognizerService(detect_every=3)

    def toggle_fullscreen(self, event=None):
        self.is_fullscreen = not getattr(self, 'is_fullscreen', False)
        self.attributes("-fullscreen", self.is_fullscreen)
        return "break"
        
    def end_fullscreen(self, event=None):
        self.is_fullscreen = False
        self.attributes("-fullscreen", False)
        return "break"

    def show_frame(self, page_name):
        frame = self.frames[page_name]
        frame.tkraise()
        if hasattr(frame, 'on_show'):
            frame.on_show()

class MainScreen(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="white")
        self.controller = controller
        
        self.center_frame = tk.Frame(self, bg="white")
        self.center_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        header_frame = tk.Frame(self.center_frame, bg="white")
        header_frame.pack(pady=10, fill=tk.X)
        
        # Place logo on the left (or centered)
        try:
            logo_img = Image.open("logo.jpeg")
            logo_img.thumbnail((160, 160))
            self.logo_photo = ImageTk.PhotoImage(logo_img)
            self.logo_label = tk.Label(header_frame, image=self.logo_photo, bg="white")
            self.logo_label.pack(pady=10)
        except Exception as e:
            print("Logo not found, text fallback used")
            self.logo_label = tk.Label(self.center_frame, text="LOGO", font=self.controller.title_font, bg="white")
            self.logo_label.pack(pady=10)
            
        # Bind hidden admin login to the logo
        self.logo_label.bind("<Button-1>", lambda e: self.controller.show_frame("AdminLoginScreen"))
        
        # Clock
        self.time_label = tk.Label(self.center_frame, text="", font=self.controller.huge_time_font, bg="white", fg="black")
        self.time_label.pack(pady=(10, 0))
        
        self.date_label = tk.Label(self.center_frame, text="", font=self.controller.header_font, bg="white", fg="black")
        self.date_label.pack(pady=(0, 40))
        
        self.update_clock()
        

        
        # Buttons
        btn_frame = tk.Frame(self.center_frame, bg="white")
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
        self.controller.show_frame("FaceIDScreen")
        
    def update_clock(self):
        try:
            now = datetime.now()
            time_str = now.strftime("%H:%M")
            
            hari_dict = {"Monday": "Senin", "Tuesday": "Selasa", "Wednesday": "Rabu", "Thursday": "Kamis", "Friday": "Jumat", "Saturday": "Sabtu", "Sunday": "Minggu"}
            bulan_dict = {"January": "Januari", "February": "Februari", "March": "Maret", "April": "April", "May": "Mei", "June": "Juni", "July": "Juli", "August": "Agustus", "September": "September", "October": "Oktober", "November": "November", "December": "Desember"}
            
            hari = hari_dict[now.strftime("%A")]
            bulan = bulan_dict[now.strftime("%B")]
            date_str = f"{hari}, {now.strftime('%d')} {bulan} {now.strftime('%Y')}"
            
            self.time_label.config(text=time_str)
            self.date_label.config(text=date_str)
            self.after(1000, self.update_clock)
        except:
            pass

class FaceIDScreen(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="white")
        self.controller = controller
        self.cap = None
        
        self.center_frame = tk.Frame(self, bg="white")
        self.center_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        tk.Label(self.center_frame, text="Scan Your Face", font=self.controller.title_font, bg="white", fg="#007bff").pack(pady=10)
        
        self.video_label = tk.Label(self.center_frame, bg="white")
        self.video_label.pack(pady=10)
        
        self.status_label = tk.Label(self.center_frame, text="", font=self.controller.normal_font, bg="white", fg="red")
        self.status_label.pack(pady=5)
                  

        
        btn_frame = tk.Frame(self, bg="white")
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=20, padx=20)
        
        MacButton(btn_frame, text="< Batal", font=self.controller.normal_font, 
                  bg="#cccccc", fg="black", borderless=1, padx=20, pady=10,
                  command=self.go_back).pack(side=tk.LEFT)
                  
        MacButton(btn_frame, text="Gunakan RFID >", font=self.controller.normal_font, 
                  bg="#ffc107", fg="black", borderless=1, padx=20, pady=10,
                  command=self.go_to_rfid).pack(side=tk.RIGHT)
                  
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
                    self.controller.led.success(3.0)
                    self.status_label.config(text=f"Welcome {recognized_name}!", fg="green")
                    self.after(1000, lambda n=recognized_name: self.process_success(n))
                    return # Stop looping
                else:
                    if results:
                        self.status_label.config(text="Wajah tidak dikenal", fg="red")
                        if not getattr(self, 'is_error_led_on', False):
                            self.controller.led.error(2.0)
                            self.is_error_led_on = True
                            self.after(2000, lambda: setattr(self, 'is_error_led_on', False))
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
        self.controller.show_frame("MainScreen")
        
    def go_to_rfid(self):
        self.stop_camera()
        self.controller.show_frame("RFIDScreen")
        
    def process_success(self, name):
        self.stop_camera()
        self.controller.current_user = name
        
        if self.controller.attendance_type == "datang":
            # API Hit Datang
            success, msg = self.controller.recognizer.record_attendance(name, method="face", attendance_type="datang")
            if not success:
                print(f"API Error: {msg}")
            self.controller.show_frame("SuccessScreen")
        else:
            # Tunda API Hit, masuk ke layar Shift
            self.controller.show_frame("ShiftMutuScreen")

class RFIDScreen(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="white")
        self.controller = controller
        
        self.center_frame = tk.Frame(self, bg="white")
        self.center_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        tk.Label(self.center_frame, text="Tempel Kartu Asisten Anda", font=self.controller.title_font, bg="white", fg="#007bff").pack(pady=50)
        
        # Simulating RFID tap for testing on laptop
        self.rfid_entry = tk.Entry(self.center_frame, font=self.controller.normal_font)
        self.rfid_entry.pack(pady=20)
        

        MacButton(self.center_frame, text="[Simulasi Tap Kartu]", bg="green", fg="white", borderless=1, padx=20, pady=10,
                  command=self.simulate_success).pack(pady=5)
                  
        btn_frame = tk.Frame(self, bg="white")
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=20, padx=20)
        MacButton(btn_frame, text="< Kembali ke Kamera", font=self.controller.normal_font, 
                  bg="#cccccc", fg="black", borderless=1, padx=20, pady=10,
                  command=self.go_back).pack(side=tk.LEFT)

    def on_show(self):
        self.rfid_entry.delete(0, tk.END)
        self.rfid_entry.focus()
        self.controller.rfid.start_scanning(self._on_rfid_success)
        
    def _on_rfid_success(self, uid, name):
        # Dipanggil oleh thread latar belakang, pastikan update UI dilakukan di Main Thread
        self.after(0, lambda: self._handle_rfid_success(uid, name))
        
    def _handle_rfid_success(self, uid, name):
        self.controller.led.success(3.0)
        self.rfid_entry.delete(0, tk.END)
        self.rfid_entry.insert(0, uid)
        self.controller.current_user = name
        if self.controller.attendance_type == "datang":
            # API Hit Datang
            success, msg = self.controller.recognizer.record_attendance(name, method="rfid", attendance_type="datang")
            if not success:
                print(f"API Error: {msg}")
            self.controller.show_frame("SuccessScreen")
        else:
            # Tunda API Hit, masuk ke layar Shift
            self.controller.show_frame("ShiftMutuScreen")
            
    def go_back(self):
        self.controller.rfid.stop_scanning()
        self.controller.show_frame("FaceIDScreen")
        
    def simulate_success(self):
        self._handle_rfid_success("SIMULATION_123", "Dimas (Asisten)")

class ShiftMutuScreen(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="white")
        self.controller = controller
        
        self.center_frame = tk.Frame(self, bg="white")
        self.center_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        self.greeting_label = tk.Label(self.center_frame, text="", font=self.controller.title_font, bg="white", fg="#007bff")
        self.greeting_label.pack(pady=(5, 5))
        
        self.subtitle_label = tk.Label(self.center_frame, text="Pilih Shift", font=self.controller.header_font, bg="white", fg="gray")
        self.subtitle_label.pack(pady=(0, 5))
        
        # Legend
        legend_text = "1: Standby | 2: Piket | 3: Teaching | 4: Rapat | 5: Riset"
        tk.Label(self.center_frame, text=legend_text, font=self.controller.normal_font, bg="white", fg="gray").pack(pady=5)
        
        self.selected_mutu_per_shift = {r: None for r in range(5)}
        self.buttons = []
        
        grid_frame = tk.Frame(self.center_frame, bg="white")
        grid_frame.pack(pady=5)
        

        
        shifts = ["SHIFT 1", "SHIFT 2", "SHIFT 3", "SHIFT 4", "SHIFT 5"]
        mutu_keys = ["stand by", "piket", "teaching", "rapat", "riset"]
        
        for r, shift in enumerate(shifts):
            tk.Label(grid_frame, text=shift, font=self.controller.large_button_font, bg="white", fg="#007bff").grid(row=r, column=0, padx=8, pady=5, sticky=tk.E)
            
            row_buttons = []
            for c, mutu in enumerate(mutu_keys):
                btn = MacButton(grid_frame, text=str(c+1), font=self.controller.large_button_font, 
                                bg="white", fg="#007bff", borderless=1, padx=20, pady=10,
                                command=lambda s=shift, m=mutu, r=r, c=c: self.select_cell(s, m, r, c))
                btn.grid(row=r, column=c+1, padx=8, pady=5)
                row_buttons.append(btn)
            self.buttons.append(row_buttons)
            
        btn_frame = tk.Frame(self.center_frame, bg="white")
        btn_frame.pack(side=tk.TOP, fill=tk.X, pady=(20, 0), padx=15)
        
        MacButton(btn_frame, text="< Batal", font=self.controller.normal_font, 
                  bg="#cccccc", fg="black", borderless=1, padx=30, pady=15,
                  command=lambda: self.controller.show_frame("MainScreen")).pack(side=tk.LEFT)
                  
        self.confirm_btn = MacButton(btn_frame, text="CONFIRM", font=self.controller.large_button_font, 
                                     bg="#cccccc", fg="black", borderless=1, padx=50, pady=15,
                                     command=self.submit)
        self.confirm_btn.pack(side=tk.RIGHT)
                  
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
            self.confirm_btn.configure(bg="green", fg="white", text="CONFIRM")
        else:
            self.confirm_btn.configure(bg="#cccccc", fg="black", text="CONFIRM")
        
    def submit(self):
        selected_mutus = [m for m in self.selected_mutu_per_shift.values() if m is not None]
        if not selected_mutus:
            self.confirm_btn.configure(text="Pilih minimal 1!", bg="red")
            self.after(1000, lambda: self.confirm_btn.configure(text="CONFIRM", bg="#cccccc"))
            return
            
        total_mutu_value = sum(MUTU_RATES[m] for m in selected_mutus)
        # Jangan hitung RP di sini, tunggu balasan dari Backend (Anti-Cheat)
        self.controller.total_rp = 0
        
        # Susun payload shifts untuk API Backend
        shifts_payload = []
        shifts_data = [
            {"label": "Shift 1", "time": "08:00 - 10:00"},
            {"label": "Shift 2", "time": "10:00 - 12:00"},
            {"label": "Shift 3", "time": "12:00 - 14:00"},
            {"label": "Shift 4", "time": "14:00 - 16:00"},
            {"label": "Shift 5", "time": "16:00 - 18:00"}
        ]
        
        for r in range(5):
            mutu = self.selected_mutu_per_shift[r]
            activity = mutu.title() if mutu else "Kosong"
            points = MUTU_RATES.get(mutu, 0) if mutu else 0
            
            shifts_payload.append({
                "shift_number": r + 1,
                "shift_label": f"{shifts_data[r]['label']} ({shifts_data[r]['time']})",
                "time_range": shifts_data[r]['time'],
                "activity": activity,
                "points": points
            })
            
        # Tembak API Absen Pulang
        success, response_data = self.controller.recognizer.record_attendance(
            self.controller.current_user, 
            method="face", # default fallback
            attendance_type="pulang", 
            shifts=shifts_payload
        )
        
        if success:
            if isinstance(response_data, dict):
                self.controller.total_rp = response_data.get("total_rp", 0)
        else:
            print(f"API Error: {response_data}")
            
        self.controller.show_frame("SuccessScreen")
        
    def on_show(self):
        user = self.controller.current_user
        self.greeting_label.config(text=f"Halo, {user}!")
        self.selected_mutu_per_shift = {r: None for r in range(5)}
        for row in self.buttons:
            for btn in row:
                btn.configure(bg="white", fg="#007bff")
        self.confirm_btn.configure(bg="#cccccc", fg="black", text="CONFIRM")

class SuccessScreen(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="white")
        self.controller = controller
        
        self.center_frame = tk.Frame(self, bg="white")
        self.center_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        self.msg_label = tk.Label(self.center_frame, text="", font=self.controller.huge_msg_font, bg="white", fg="#007bff", justify=tk.CENTER)
        self.msg_label.pack(pady=20)
        
        self.mutu_frame = tk.Frame(self.center_frame, bg="#ffc107", padx=8, pady=8) # Yellow border
        
        self.mutu_label = tk.Label(self.mutu_frame, text="", font=self.controller.title_font, bg="white", fg="black", justify=tk.CENTER, padx=30, pady=20)
        self.mutu_label.pack()
        
    def on_show(self):
        user = self.controller.current_user
        if self.controller.attendance_type == "datang":
            msg = f"Have a great day,\n{user}!"
            self.msg_label.config(text=msg)
            self.mutu_frame.pack_forget()
        else:
            rp = getattr(self.controller, 'total_rp', 0)
            msg = f"You did so well today.\nGet home safe, okay?"
            self.msg_label.config(text=msg)
            
            mutu_msg = f"Estimasi Total Mutu\nRp {rp:,}"
            self.mutu_label.config(text=mutu_msg)
            self.mutu_frame.pack(pady=30)
            
        # Auto redirect back to main screen after 4 seconds
        self.after(4000, lambda: self.controller.show_frame("MainScreen"))

class AdminLoginScreen(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="white")
        self.controller = controller
        
        self.center_frame = tk.Frame(self, bg="white")
        self.center_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        tk.Label(self.center_frame, text="Admin PIN", font=self.controller.title_font, bg="white", fg="black").pack(pady=20)
        
        self.pin_var = tk.StringVar()
        self.pin_display = tk.Label(self.center_frame, textvariable=self.pin_var, font=self.controller.title_font, bg="#f0f0f0", fg="#007bff", width=10)
        self.pin_display.pack(pady=20)
        
        grid_frame = tk.Frame(self.center_frame, bg="white")
        grid_frame.pack()
        
        keys = [
            ['1', '2', '3'],
            ['4', '5', '6'],
            ['7', '8', '9'],
            ['Clear', '0', 'OK']
        ]
        

        for r, row in enumerate(keys):
            for c, key in enumerate(row):
                btn = MacButton(grid_frame, text=key, font=self.controller.large_button_font,
                                bg="#e0e0e0", fg="black", borderless=1, padx=20, pady=20,
                                command=lambda k=key: self.press(k))
                btn.grid(row=r, column=c, padx=10, pady=10)
                
        btn_frame = tk.Frame(self, bg="white")
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=30, padx=30)
        MacButton(btn_frame, text="< Batal", font=self.controller.normal_font, 
                  bg="#cccccc", fg="black", borderless=1, padx=30, pady=15,
                  command=self.cancel).pack(side=tk.LEFT)
                  
    def on_show(self):
        self.pin_var.set("")
                  
    def press(self, key):
        if key == 'Clear':
            self.pin_var.set("")
        elif key == 'OK':
            if self.pin_var.get() == "123":
                self.pin_var.set("")
                self.launch_register()
            else:
                self.pin_var.set("SALAH")
                self.after(1000, lambda: self.pin_var.set(""))
        else:
            current = self.pin_var.get()
            if current == "SALAH": current = ""
            if len(current) < 6:
                self.pin_var.set(current + key)
                
    def cancel(self):
        self.pin_var.set("")
        self.controller.show_frame("MainScreen")
        
    def launch_register(self):
        import subprocess
        import sys
        import threading
        
        self.controller.show_frame("MainScreen")
        was_fullscreen = self.controller.attributes("-fullscreen")
        
        # Sembunyikan Kiosk GUI sepenuhnya agar aplikasi Register bisa muncul ke depan
        self.controller.withdraw()
            
        def run_app():
            subprocess.run([sys.executable, "get_faces_from_camera_tkinter.py"])
            
            def restore_kiosk():
                self.controller.deiconify()
                # Angkat kembali window kiosk ke paling depan
                self.controller.lift()
                self.controller.focus_force()
                if was_fullscreen:
                    self.controller.attributes("-fullscreen", True)
                    
            self.controller.after(0, restore_kiosk)
                
        threading.Thread(target=run_app, daemon=True).start()

if __name__ == "__main__":
    app = KioskGUI()
    app.mainloop()
