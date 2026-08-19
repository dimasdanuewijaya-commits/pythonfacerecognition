import dlib
import numpy as np
import cv2
import os
import shutil
import time
import logging
import tkinter as tk
from tkinter import font as tkFont
from tkinter import messagebox, ttk
from PIL import Image, ImageTk

# ─── Dlib face detector ───────────────────────────────────────────────────────
detector = dlib.get_frontal_face_detector()

# ─── Design constants ─────────────────────────────────────────────────────────
BG_COLOR      = "#1a1a2e"
PANEL_COLOR   = "#16213e"
ACCENT_COLOR  = "#0f3460"
GREEN_COLOR   = "#4ade80"
RED_COLOR     = "#f87171"
YELLOW_COLOR  = "#fbbf24"
WHITE_COLOR   = "#f1f5f9"
MUTED_COLOR   = "#94a3b8"
BTN_PRIMARY   = "#0ea5e9"
BTN_DANGER    = "#ef4444"
BTN_SUCCESS   = "#22c55e"

CAM_WIDTH     = 480
CAM_HEIGHT    = 360
# Kamera juga di-set ke resolusi ini dari awal agar lebih ringan
DETECT_EVERY  = 3   # Jalankan face detection hanya setiap N frame (hemat CPU)


class Face_Register:
    def __init__(self):
        self.current_frame_faces_cnt = 0
        self.existing_faces_cnt      = 0
        self.ss_cnt                  = 0
        self.frame_cnt               = 0

        self.path_photos_from_camera = "data/data_faces_from_camera/"
        self.current_face_dir        = ""
        self.input_name_char         = ""
        self.font                    = cv2.FONT_HERSHEY_SIMPLEX

        self.current_frame           = None
        self.face_ROI_width_start    = 0
        self.face_ROI_height_start   = 0
        self.face_ROI_width          = 0
        self.face_ROI_height         = 0
        self.ww = self.hh            = 0
        self.detected_faces          = []   # Cache hasil deteksi

        self.out_of_range_flag       = False
        self.face_folder_created_flag= False

        # FPS
        self.frame_time              = 0
        self.frame_start_time        = time.time()
        self.fps                     = 0

        # ── Kamera ─────────────────────────────────────────────────────────
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAM_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)       # Kurangi buffer delay

        # ── Tkinter ────────────────────────────────────────────────────────
        self._build_window()

    # ─────────────────────────────────────────────────────────────────────────
    # BUILD UI
    # ─────────────────────────────────────────────────────────────────────────
    def _build_window(self):
        self.win = tk.Tk()
        self.win.title("Face Register")
        self.win.configure(bg=BG_COLOR)
        self.win.attributes("-fullscreen", True)
        
        # Center wrapper
        self.wrapper = tk.Frame(self.win, bg=BG_COLOR)
        self.wrapper.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        # Force focus on macOS
        self.win.lift()
        self.win.attributes('-topmost', True)
        self.win.after_idle(self.win.attributes, '-topmost', False)
        self.win.focus_force()

        # ── Fonts ──────────────────────────────────────────────────────────
        self.font_title   = tkFont.Font(family='Helvetica', size=24, weight='bold')
        self.font_label   = tkFont.Font(family='Helvetica', size=14)
        self.font_step    = tkFont.Font(family='Helvetica', size=16, weight='bold')
        self.font_mono    = tkFont.Font(family='Courier',   size=14)
        self.font_big_num = tkFont.Font(family='Helvetica', size=36, weight='bold')

        # ── Header bar ─────────────────────────────────────────────────────
        header = tk.Frame(self.wrapper, bg=ACCENT_COLOR, height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        lbl_title = tk.Label(header, text="Face Register", font=self.font_title,
                             bg=ACCENT_COLOR, fg=WHITE_COLOR)
        lbl_title.pack(side=tk.LEFT, padx=20, pady=10)
        
        btn_close = tk.Button(header, text="Kembali ke Kiosk", font=self.font_label,
                              bg=RED_COLOR, fg=WHITE_COLOR, cursor="hand2",
                              command=self.win.destroy)
        btn_close.pack(side=tk.RIGHT, padx=20, pady=10)

        # ── Main body ──────────────────────────────────────────────────────
        body = tk.Frame(self.wrapper, bg=BG_COLOR)
        body.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        # Top: camera
        left = tk.Frame(body, bg=BG_COLOR)
        left.pack(side=tk.TOP, fill=tk.BOTH)

        cam_border = tk.Frame(left, bg=ACCENT_COLOR, bd=2, relief=tk.FLAT)
        cam_border.pack()
        self.lbl_camera = tk.Label(cam_border, bg="black",
                                   width=CAM_WIDTH, height=CAM_HEIGHT)
        self.lbl_camera.pack()

        # Status bar below camera
        status_bar = tk.Frame(left, bg=PANEL_COLOR)
        status_bar.pack(fill=tk.X, pady=(6, 0))

        self.lbl_fps = tk.Label(status_bar, text="FPS: —", font=self.font_mono,
                                bg=PANEL_COLOR, fg=GREEN_COLOR, padx=10)
        self.lbl_fps.pack(side=tk.LEFT)

        self.lbl_face_cnt = tk.Label(status_bar, text="Faces: 0", font=self.font_mono,
                                     bg=PANEL_COLOR, fg=YELLOW_COLOR, padx=10)
        self.lbl_face_cnt.pack(side=tk.LEFT)

        self.lbl_range_warn = tk.Label(status_bar, text="", font=self.font_mono,
                                       bg=PANEL_COLOR, fg=RED_COLOR, padx=10)
        self.lbl_range_warn.pack(side=tk.LEFT)

        # Bottom: control panel
        right = tk.Frame(body, bg=PANEL_COLOR, bd=0)
        right.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(18, 0))

        self._build_right_panel(right)

    def _card(self, parent, title, row_offset=0):
        """Helper: creates a labelled card section."""
        sep = tk.Frame(parent, bg=ACCENT_COLOR, height=1)
        sep.pack(fill=tk.X, padx=12, pady=(12, 0))
        tk.Label(parent, text=title, font=self.font_step,
                 bg=PANEL_COLOR, fg=BTN_PRIMARY).pack(anchor=tk.W, padx=16, pady=(6, 2))

    def _btn(self, parent, text, command, color=BTN_PRIMARY, fg=WHITE_COLOR, **kw):
        b = tk.Button(parent, text=text, command=command,
                      font=self.font_label,
                      cursor="hand2", padx=12, pady=6, **kw)
        return b

    def _build_right_panel(self, panel):
        # ── Stats ──────────────────────────────────────────────────────────
        stats = tk.Frame(panel, bg=PANEL_COLOR)
        stats.pack(fill=tk.X, padx=12, pady=12)

        tk.Label(stats, text="People in Database",
                 font=self.font_label, bg=PANEL_COLOR, fg=MUTED_COLOR).pack()
        self.lbl_db_count = tk.Label(stats, text="—", font=self.font_big_num,
                                     bg=PANEL_COLOR, fg=WHITE_COLOR)
        self.lbl_db_count.pack()

        tk.Label(stats, text="Photos saved (current person)",
                 font=self.font_label, bg=PANEL_COLOR, fg=MUTED_COLOR).pack(pady=(8, 0))
        self.lbl_ss_count = tk.Label(stats, text="0", font=self.font_big_num,
                                     bg=PANEL_COLOR, fg=GREEN_COLOR)
        self.lbl_ss_count.pack()

        # ── Step 1 ─────────────────────────────────────────────────────────
        self._card(panel, "Step 1 — Clear All Data")
        self._btn(panel, "🗑  Clear All Faces", self.GUI_clear_data,
                  color=BTN_DANGER).pack(fill=tk.X, padx=16, pady=(4, 0))

        # ── Step 2 ─────────────────────────────────────────────────────────
        self._card(panel, "Step 2 — Register New Person")

        name_row = tk.Frame(panel, bg=PANEL_COLOR)
        name_row.pack(fill=tk.X, padx=16, pady=(4, 0))
        tk.Label(name_row, text="Name:", font=self.font_label,
                 bg=PANEL_COLOR, fg=MUTED_COLOR).pack(side=tk.LEFT)
        self.input_name = tk.Entry(name_row, font=self.font_label,
                                   bg=ACCENT_COLOR, fg=WHITE_COLOR,
                                   insertbackground=WHITE_COLOR,
                                   relief=tk.FLAT, bd=4)
        self.input_name.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
        self.input_name.bind("<Return>", lambda e: self.GUI_get_input_name())

        self._btn(panel, "➕  Create Folder", self.GUI_get_input_name,
                  color=BTN_PRIMARY).pack(fill=tk.X, padx=16, pady=(6, 0))

        # ── Step 3 ─────────────────────────────────────────────────────────
        self._card(panel, "Step 3 — Capture Photo")

        hint = tk.Label(panel,
                        text="Position your face inside the box,\nthen click Capture.",
                        font=self.font_label, bg=PANEL_COLOR, fg=MUTED_COLOR,
                        justify=tk.LEFT)
        hint.pack(anchor=tk.W, padx=16, pady=(4, 0))

        self._btn(panel, "📸  Capture Face", self.save_current_face,
                  color=BTN_SUCCESS).pack(fill=tk.X, padx=16, pady=(6, 0))

        # ── Log ────────────────────────────────────────────────────────────
        sep = tk.Frame(panel, bg=ACCENT_COLOR, height=1)
        sep.pack(fill=tk.X, padx=12, pady=12)
        self.lbl_log = tk.Label(panel, text="Ready.", font=self.font_mono,
                                bg=PANEL_COLOR, fg=GREEN_COLOR,
                                wraplength=260, justify=tk.LEFT)
        self.lbl_log.pack(anchor=tk.W, padx=16)

        # ── Bottom Action ──────────────────────────────────────────────────
        btn_close = tk.Button(panel, text="⬅ Kembali ke Kiosk", command=self.win.destroy,
                              font=self.font_step, bg=RED_COLOR, fg=WHITE_COLOR,
                              cursor="hand2", padx=12, pady=10, relief=tk.FLAT)
        btn_close.pack(fill=tk.X, side=tk.BOTTOM, padx=16, pady=20)
        
    # ─────────────────────────────────────────────────────────────────────────
    # BUSINESS LOGIC
    # ─────────────────────────────────────────────────────────────────────────
    def GUI_clear_data(self):
        if not messagebox.askyesno("Confirm", "Delete ALL face data and CSV?"):
            return
        for folder in os.listdir(self.path_photos_from_camera):
            path = os.path.join(self.path_photos_from_camera, folder)
            if os.path.isdir(path):
                shutil.rmtree(path)
        if os.path.isfile("data/features_all.csv"):
            os.remove("data/features_all.csv")
        self.existing_faces_cnt = 0
        self.lbl_db_count["text"] = "0"
        self._log("All data cleared.", color=RED_COLOR)

    def GUI_get_input_name(self):
        self.input_name_char = self.input_name.get().strip()
        if not self.input_name_char:
            self._log("Please enter a name first!", color=RED_COLOR)
            return
        self.create_face_folder()
        self.lbl_db_count["text"] = str(self.existing_faces_cnt)

    def _log(self, msg, color=GREEN_COLOR):
        self.lbl_log["text"] = msg
        self.lbl_log["fg"]   = color

    def pre_work_mkdir(self):
        os.makedirs(self.path_photos_from_camera, exist_ok=True)

    def check_existing_faces_cnt(self):
        persons = [d for d in os.listdir(self.path_photos_from_camera)
                   if os.path.isdir(os.path.join(self.path_photos_from_camera, d))]
        if persons:
            nums = []
            for p in persons:
                try:
                    nums.append(int(p.split('_')[1]))
                except (IndexError, ValueError):
                    pass
            self.existing_faces_cnt = max(nums) if nums else 0
        else:
            self.existing_faces_cnt = 0
        self.lbl_db_count["text"] = str(self.existing_faces_cnt)

    def update_fps(self):
        now = time.time()
        elapsed = now - self.frame_start_time
        self.fps = 1.0 / elapsed if elapsed > 0 else 0
        self.frame_start_time = now
        self.lbl_fps["text"] = f"FPS: {self.fps:.1f}"

    def create_face_folder(self):
        self.existing_faces_cnt += 1
        folder_name = f"person_{self.existing_faces_cnt}_{self.input_name_char}"
        self.current_face_dir = os.path.join(self.path_photos_from_camera, folder_name)
        os.makedirs(self.current_face_dir, exist_ok=True)
        self.ss_cnt = 0
        self.lbl_ss_count["text"] = "0"
        self.face_folder_created_flag = True
        self._log(f"Folder created:\n{folder_name}")
        logging.info("Created folder: %s", self.current_face_dir)

    def save_current_face(self):
        if not self.face_folder_created_flag:
            self._log("Run Step 2 first!", color=RED_COLOR)
            return
        if self.current_frame_faces_cnt != 1:
            self._log("Need exactly 1 face in frame!", color=YELLOW_COLOR)
            return
        if self.out_of_range_flag:
            self._log("Face out of range! Move closer to center.", color=RED_COLOR)
            return

        self.ss_cnt += 1
        # Fast numpy crop instead of pixel-by-pixel loop
        t, b = self.face_ROI_height_start, self.face_ROI_height_start + self.face_ROI_height
        l, r = self.face_ROI_width_start,  self.face_ROI_width_start + self.face_ROI_width
        pad_y = self.hh
        pad_x = self.ww
        h, w  = self.current_frame.shape[:2]
        t_pad = max(0, t - pad_y)
        b_pad = min(h, b + pad_y)
        l_pad = max(0, l - pad_x)
        r_pad = min(w, r + pad_x)

        face_crop = self.current_frame[t_pad:b_pad, l_pad:r_pad]
        # current_frame is already RGB from get_frame; convert to BGR for imwrite
        face_bgr  = cv2.cvtColor(face_crop, cv2.COLOR_RGB2BGR)
        save_path = os.path.join(self.current_face_dir, f"img_face_{self.ss_cnt}.jpg")
        cv2.imwrite(save_path, face_bgr)

        self.lbl_ss_count["text"] = str(self.ss_cnt)
        self._log(f"✅ Saved: img_face_{self.ss_cnt}.jpg")
        logging.info("Saved: %s", save_path)

    def get_frame(self):
        if self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.flip(frame, 1)  # Mirror / selfie view
                frame = cv2.resize(frame, (CAM_WIDTH, CAM_HEIGHT),
                                   interpolation=cv2.INTER_LINEAR)
                return ret, cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return False, None

    # ─── Main loop ────────────────────────────────────────────────────────────
    def process(self):
        self.frame_cnt += 1
        ret, self.current_frame = self.get_frame()

        if ret:
            self.update_fps()

            # ── Face detection: only every DETECT_EVERY frames ────────────
            if self.frame_cnt % DETECT_EVERY == 0:
                self.detected_faces = detector(self.current_frame, 0)
                self.current_frame_faces_cnt = len(self.detected_faces)
                self.lbl_face_cnt["text"] = f"Faces: {self.current_frame_faces_cnt}"

            # ── Draw bounding boxes ───────────────────────────────────────
            display = self.current_frame.copy()
            for k, d in enumerate(self.detected_faces):
                self.face_ROI_width_start  = d.left()
                self.face_ROI_height_start = d.top()
                self.face_ROI_height = d.bottom() - d.top()
                self.face_ROI_width  = d.right()  - d.left()
                self.hh = self.face_ROI_height // 2
                self.ww = self.face_ROI_width  // 2

                out = ((d.right() + self.ww) > CAM_WIDTH  or
                       (d.bottom() + self.hh) > CAM_HEIGHT or
                       (d.left() - self.ww)  < 0          or
                       (d.top()  - self.hh)  < 0)

                if out:
                    self.out_of_range_flag = True
                    self.lbl_range_warn["text"] = "⚠ OUT OF RANGE"
                    color = (248, 113, 113)  # red
                else:
                    self.out_of_range_flag = False
                    self.lbl_range_warn["text"] = ""
                    color = (74, 222, 128)   # green

                # Outer guidance box
                cv2.rectangle(display,
                              (d.left() - self.ww, d.top() - self.hh),
                              (d.right() + self.ww, d.bottom() + self.hh),
                              color, 1)
                # Inner tight box
                cv2.rectangle(display,
                              (d.left(), d.top()),
                              (d.right(), d.bottom()),
                              color, 2)
                cv2.putText(display, f"Face {k+1}",
                            (d.left(), d.top() - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1)

            # ── Overlay HUD ───────────────────────────────────────────────
            cv2.putText(display, f"Photos: {self.ss_cnt}", (8, 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)

            # ── Push to Tkinter label ─────────────────────────────────────
            img = ImageTk.PhotoImage(Image.fromarray(display))
            self.lbl_camera.img_tk = img
            self.lbl_camera.configure(image=img)

        self.win.after(16, self.process)   # ~60 FPS target

    # ─────────────────────────────────────────────────────────────────────────
    def run(self):
        self.pre_work_mkdir()
        self.check_existing_faces_cnt()
        self.process()
        self.win.mainloop()
        self.cap.release()


def main():
    logging.basicConfig(level=logging.INFO)
    Face_Register_con = Face_Register()
    Face_Register_con.run()


if __name__ == '__main__':
    main()
