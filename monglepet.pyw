import tkinter as tk
from tkinter import messagebox
import json, os, time, math, random
from pathlib import Path

APP_NAME = "몽글펫"
SAVE_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "MonglePet"
SAVE_FILE = SAVE_DIR / "save.json"
KEY = "#ff00ff"
W, H = 110, 100
PET_W, PET_H = 76, 80
DEFAULT = {
    "name": "몽글이", "age_seconds": 0, "hunger": 84.0, "happiness": 84.0,
    "energy": 84.0, "coins": 80, "xp": 0,
    "items": {"간식": 3, "장난감": 1}, "last_saved": time.time(),
    "x": 180, "y": 500, "evolution": 0
}

def clamp(v, lo=0, hi=100):
    return max(lo, min(hi, v))

class DeskPet:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry(f"{W}x{H}+180+500")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=KEY)
        try:
            self.root.wm_attributes("-transparentcolor", KEY)
        except tk.TclError:
            pass
        self.data = self.load_data()
        self.drag_start = None
        self.dragging = False
        self.physics = False
        self.vy = 0.0
        self.action = "idle"
        self.action_until = 0
        self.direction = random.choice([-1, 1])
        self.walking = True
        self.next_turn = time.time() + random.uniform(2.0, 5.0)
        self.last_tick = time.time()
        self.blink_until = 0
        # Native tk.Menu 대신 둥근 파스텔 커스텀 팝업을 사용합니다.
        self.menu_window = None
        self.canvas = tk.Canvas(root, width=W, height=H, bg=KEY, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.do_drag)
        self.canvas.bind("<ButtonRelease-1>", self.end_drag)
        self.canvas.bind("<Button-3>", self.popup_menu)
        self.canvas.bind("<Button-2>", self.popup_menu)
        self.root.bind("<Escape>", lambda e: self.close())
        self.apply_offline_time()
        self.restore_position()
        self.snap_to_taskbar_if_needed()
        self.refresh()
        self.tick()

    def load_data(self):
        try:
            SAVE_DIR.mkdir(parents=True, exist_ok=True)
            if SAVE_FILE.exists():
                d = json.loads(SAVE_FILE.read_text(encoding="utf-8"))
                for k, v in DEFAULT.items():
                    if k not in d: d[k] = v.copy() if isinstance(v, dict) else v
                if not isinstance(d.get("items"), dict): d["items"] = {"간식": 3, "장난감": 1}
                d["items"].setdefault("간식", 3); d["items"].setdefault("장난감", 1)
                return d
        except Exception:
            pass
        return json.loads(json.dumps(DEFAULT, ensure_ascii=False))

    def taskbar_y(self):
        # 기본 Windows 작업 표시줄(화면 아래쪽) 바로 위를 걷습니다.
        return max(0, self.root.winfo_screenheight() - H - 48)

    def save_data(self):
        try:
            SAVE_DIR.mkdir(parents=True, exist_ok=True)
            self.data["last_saved"] = time.time()
            self.data["x"], self.data["y"] = self.root.winfo_x(), self.root.winfo_y()
            SAVE_FILE.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def apply_offline_time(self):
        elapsed = max(0, min(time.time() - float(self.data.get("last_saved", time.time())), 7*24*3600))
        hours = elapsed / 3600
        self.data["age_seconds"] = self.data.get("age_seconds", 0) + elapsed
        self.data["hunger"] = clamp(self.data.get("hunger", 80) - hours * 4)
        self.data["happiness"] = clamp(self.data.get("happiness", 80) - hours * 2.5)
        self.data["energy"] = clamp(self.data.get("energy", 80) - hours * 1.8)
        self.data["last_saved"] = time.time()

    def restore_position(self):
        try:
            x = int(self.data.get("x", 180)); y = self.taskbar_y()
            x = max(0, min(self.root.winfo_screenwidth()-W, x))
            self.root.geometry(f"{W}x{H}+{x}+{y}")
        except Exception:
            pass

    def snap_to_taskbar_if_needed(self):
        x, y = self.root.winfo_x(), self.root.winfo_y()
        if y > self.taskbar_y() + 25 or y < 0:
            self.root.geometry(f"+{max(0, min(self.root.winfo_screenwidth()-W, x))}+{self.taskbar_y()}")

    def start_drag(self, e):
        self.drag_start = (e.x_root, e.y_root, self.root.winfo_x(), self.root.winfo_y(), time.time())
        self.dragging = False
        self.walking = False
        self.physics = False

    def do_drag(self, e):
        if not self.drag_start: return
        dx, dy = e.x_root-self.drag_start[0], e.y_root-self.drag_start[1]
        if abs(dx) + abs(dy) > 4: self.dragging = True
        self.root.geometry(f"+{max(0, min(self.root.winfo_screenwidth()-W, self.drag_start[2]+dx))}+{max(0, self.drag_start[3]+dy)}")
        if self.dragging:
            self.action = "falling" if dy > 0 else "held"
        self.refresh()

    def end_drag(self, e):
        if not self.drag_start: return
        was_dragging = self.dragging
        dx, dy = e.x_root-self.drag_start[0], e.y_root-self.drag_start[1]
        self.drag_start = None
        if not was_dragging:
            self.data["happiness"] = clamp(self.data["happiness"] + 2)
            self.data["xp"] += 1
            self.action, self.action_until = "happy", time.time()+1.2
            self.walking = True
        else:
            # 놓으면 중력으로 떨어져 작업 표시줄에 닿은 뒤 일어납니다.
            self.physics = True
            self.vy = max(2.0, min(15.0, abs(dy)*0.15 + 2.0))
            self.action = "falling"
        self.save_data(); self.refresh()

    def popup_menu(self, e):
        self.walking = False
        if self.menu_window and self.menu_window.winfo_exists():
            self.menu_window.destroy()
        win = tk.Toplevel(self.root)
        self.menu_window = win
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg="#c5dff6")
        outer = tk.Frame(win, bg="#c5dff6", padx=2, pady=2)
        outer.pack(fill="both", expand=True)
        panel = tk.Frame(outer, bg="#fffdfb", padx=8, pady=8)
        panel.pack(fill="both", expand=True)
        tk.Label(panel, text="🐾  몽글펫 메뉴", bg="#eaf5ff", fg="#315b86",
                 font=("맑은 고딕", 10, "bold"), anchor="w", padx=8, pady=6).pack(fill="x", pady=(0, 5))
        actions = [
            ("🍙", "밥 주기", self.feed), ("🧸", "놀아주기 · 코인 +5", self.play),
            ("💃", "파스타 댄스", lambda: self.do_action("dance", 2.5)),
            ("🏃", "신나게 달리기", lambda: self.do_action("run", 2.0)),
            ("🙇", "꾸벅 인사하기", lambda: self.do_action("bow", 1.5)),
            ("✨", "폴짝 뛰기", lambda: self.do_action("jump", 1.6)),
            ("😭", "엉엉 울기", lambda: self.do_action("cry", 2.0)),
            ("🌞", "기지개 켜기", lambda: self.do_action("stretch", 1.8)),
            ("💤", "낮잠 자기", self.sleep_pet),
            ("💗", "상태 확인", self.show_status), ("🛍️", "간식 상점", self.open_shop),
            ("💾", "지금 저장", self.save_data), ("⏻", "종료", self.close),
        ]
        for emoji, label, command in actions:
            b = tk.Button(panel, text=f"{emoji}   {label}", anchor="w", command=lambda fn=command, w=win: self.run_menu_command(fn, w),
                          relief="flat", bd=0, bg="#fffdfb", fg="#35465b", activebackground="#e8f4ff",
                          activeforeground="#244d79", font=("맑은 고딕", 9), padx=9, pady=4, cursor="hand2")
            b.pack(fill="x", pady=1)
            b.bind("<Enter>", lambda ev, btn=b: btn.configure(bg="#e8f4ff"))
            b.bind("<Leave>", lambda ev, btn=b: btn.configure(bg="#fffdfb"))
        tk.Label(panel, text=f"🪙 {self.data['coins']} 코인  ·  Lv.{1+int(self.data['xp']//50)}",
                 bg="#f2f8ff", fg="#6d8baa", font=("맑은 고딕", 8), pady=5).pack(fill="x", pady=(5, 0))
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        px = min(max(4, e.x_root), sw-win.winfo_reqwidth()-4)
        py = min(max(4, e.y_root- win.winfo_reqheight()), sh-win.winfo_reqheight()-4)
        win.geometry(f"+{px}+{py}")
        win.bind("<Escape>", lambda ev: self.close_menu())
        win.bind("<FocusOut>", lambda ev: self.root.after(180, self.close_menu_if_unfocused))
        win.focus_force()

    def run_menu_command(self, fn, win):
        try: win.destroy()
        except Exception: pass
        self.menu_window = None
        self.walking = True
        fn()

    def close_menu(self):
        if self.menu_window and self.menu_window.winfo_exists(): self.menu_window.destroy()
        self.menu_window = None
        self.walking = True

    def close_menu_if_unfocused(self):
        try:
            if self.menu_window and self.menu_window.winfo_exists() and self.root.focus_displayof() is None:
                self.close_menu()
        except Exception: pass

    def do_action(self, name, duration=2.0):
        self.action, self.action_until = name, time.time()+duration
        if name in ("run", "dance", "jump"): self.data["happiness"] = clamp(self.data["happiness"]+3)
        self.data["xp"] += 1
        self.save_data(); self.refresh()

    def stage(self):
        days = self.data.get("age_seconds", 0) / 86400
        level = 1 + int(self.data.get("xp", 0)//50)
        if days < 1 and level < 3: return "아기"
        if days < 3 and level < 6: return "꼬마"
        if days < 7 and level < 12: return "쑥쑥"
        return "반짝 어른"

    def feed(self):
        if self.data["items"].get("간식", 0) <= 0:
            messagebox.showinfo("간식이 없어요", "우클릭 → 간식 상점에서 구매해 줘.", parent=self.root); return
        self.data["items"]["간식"] -= 1
        self.data["hunger"] = clamp(self.data["hunger"] + 27)
        self.data["happiness"] = clamp(self.data["happiness"] + 5)
        self.data["xp"] += 5
        self.action, self.action_until = "eat", time.time()+1.6
        self.save_data(); self.refresh()

    def play(self):
        if self.data["energy"] < 12:
            messagebox.showinfo("조금 쉬자", "몽글이가 피곤해. 먼저 낮잠을 재워 줘.", parent=self.root); return
        self.data["happiness"] = clamp(self.data["happiness"] + 18)
        self.data["energy"] = clamp(self.data["energy"] - 10)
        self.data["hunger"] = clamp(self.data["hunger"] - 5)
        self.data["xp"] += 8; self.data["coins"] += 5
        self.action, self.action_until = "play", time.time()+2.2
        self.save_data(); self.refresh()

    def sleep_pet(self):
        self.data["energy"] = clamp(self.data["energy"] + 30)
        self.action, self.action_until = "sleep", time.time()+3
        self.save_data(); self.refresh()

    def show_status(self):
        d = self.data
        level = 1 + int(d.get("xp", 0) // 50)
        progress = int(d.get("xp", 0) % 50)
        win = tk.Toplevel(self.root)
        win.title("몽글펫 상태")
        win.geometry("300x285")
        win.resizable(False, False)
        win.configure(bg="#fffaf3")
        win.attributes("-topmost", True)
        tk.Label(win, text=f"🐾 몽글이 · {self.stage()}", bg="#eaf5ff", fg="#315b86",
                 font=("맑은 고딕", 12, "bold"), pady=10).pack(fill="x", padx=12, pady=(12, 8))
        tk.Label(win, text=f"Lv. {level}   다음 레벨까지 {50-progress} XP", bg="#fffaf3",
                 fg="#35465b", font=("맑은 고딕", 10, "bold")).pack(anchor="w", padx=18)
        bar = tk.Canvas(win, width=260, height=18, bg="#e7eaf0", highlightthickness=0)
        bar.pack(padx=18, pady=(6, 10))
        bar.create_rectangle(0, 0, 260 * progress / 50, 18, fill="#78b8e8", outline="")
        bar.create_text(130, 9, text=f"{progress}/50 XP", fill="#254b70", font=("맑은 고딕", 8, "bold"))
        for label, value, color in [("🍙 포만감", d["hunger"], "#e9b85e"), ("😊 행복", d["happiness"], "#e99bb7"), ("⚡ 기력", d["energy"], "#78b8e8")]:
            row = tk.Frame(win, bg="#fffaf3"); row.pack(fill="x", padx=18, pady=2)
            tk.Label(row, text=label, bg="#fffaf3", fg="#35465b", font=("맑은 고딕", 9), width=10, anchor="w").pack(side="left")
            tk.Label(row, text=f"{int(value)}%", bg="#fffaf3", fg=color, font=("맑은 고딕", 9, "bold")).pack(side="right")
        tk.Label(win, text=f"🪙 {d['coins']} 코인   🍡 간식 {d['items'].get('간식',0)}개   🧸 장난감 {d['items'].get('장난감',0)}개",
                 bg="#f2f8ff", fg="#6d8baa", font=("맑은 고딕", 8), pady=8).pack(fill="x", padx=12, pady=(8, 10))

    def open_shop(self):
        win = tk.Toplevel(self.root); win.title("몽글펫 간식 상점"); win.geometry("300x220")
        win.configure(bg="#fffaf3"); win.attributes("-topmost", True)
        tk.Label(win, text=f"🪙 보유 코인: {self.data['coins']}", bg="#fffaf3", font=("맑은 고딕", 11, "bold")).pack(pady=10)
        for item, label, price, amount in [("간식", "🍡 간식 3개", 15, 3), ("장난감", "🧸 장난감 1개", 25, 1)]:
            row = tk.Frame(win, bg="#fffaf3"); row.pack(fill="x", padx=14, pady=6)
            tk.Label(row, text=f"{label} · {price} 코인", bg="#fffaf3", font=("맑은 고딕", 9)).pack(side="left")
            tk.Button(row, text="구매", command=lambda i=item,p=price,a=amount,w=win: self.buy_item(i,p,a,w), bd=0, bg="#f1d9e3", padx=9).pack(side="right")
        tk.Label(win, text="같이 놀면 코인을 얻을 수 있어요!", bg="#fffaf3", fg="#8b7d75", font=("맑은 고딕", 8)).pack(pady=7)

    def buy_item(self, item, price, amount, win):
        if self.data["coins"] < price:
            messagebox.showinfo("코인 부족", "몽글이와 놀면서 코인을 모아 봐!", parent=win); return
        self.data["coins"] -= price
        self.data["items"][item] = self.data["items"].get(item, 0) + amount
        self.save_data(); self.refresh()
        # 구매 즉시 인벤토리와 코인 수량만 갱신하고, 완료/상태 팝업은 띄우지 않습니다.
        try:
            for child in win.winfo_children():
                if isinstance(child, tk.Label) and "보유 코인" in child.cget("text"):
                    child.configure(text=f"🪙 보유 코인: {self.data['coins']}")
        except Exception:
            pass

    def draw_pet(self):
        c = self.canvas
        c.delete("all")
        t = time.time()
        sleeping = self.action == "sleep" and t < self.action_until
        happy = self.action in ("happy", "play", "eat", "stand", "dance", "run", "jump", "stretch") and t < self.action_until
        falling = self.action in ("falling", "held")
        active = self.action if t < self.action_until else "idle"
        bob = math.sin(t*13)*3.0 if active == "dance" else math.sin(t*17)*2.5 if active == "run" else math.sin(t*10)*4 if active == "jump" else math.sin(t*7)*1.5 if self.walking and not sleeping else (0 if falling else math.sin(t*3)*1.0)
        squish = 0.76 if self.action == "land" and t < self.action_until else (0.91 if active == "bow" else 1.0)
        level = 1 + int(self.data.get("xp", 0)//50)
        scale = 0.94 + min(0.22, max(0, level-1)*0.014)
        cx, cy = W//2, 47 + bob
        if falling: cy += 5
        if active == "bow": cy += 3
        if active == "stretch": cy -= 2
        outline = "#34465b"
        white = "#fffdfb"
        blue = "#6d9fc9"
        blue_light = "#9bc5e6"
        # 부드러운 바닥 그림자
        c.create_oval(cx-27, 87, cx+27, 93, fill="#e4e8ee", outline="")
        # 몸통과 작은 발: 진한 외곽선으로 아이콘 크기에서도 형태가 또렷하게
        c.create_oval(cx-22*scale, cy+8*scale, cx+22*scale, cy+34*scale*squish,
                      fill=white, outline=outline, width=1.7)
        c.create_oval(cx-8*scale, cy+27*scale, cx-1*scale, cy+32*scale,
                      fill="#f4e9e8", outline=outline, width=1)
        c.create_oval(cx+1*scale, cy+27*scale, cx+8*scale, cy+32*scale,
                      fill="#f4e9e8", outline=outline, width=1)
        # 귀와 둥근 머리 실루엣
        c.create_polygon(cx-23*scale, cy-8*scale, cx-25*scale, cy-22*scale,
                         cx-19*scale, cy-30*scale, cx-9*scale, cy-28*scale,
                         cx, cy-20*scale, cx+10*scale, cy-29*scale,
                         cx+20*scale, cy-28*scale, cx+25*scale, cy-19*scale,
                         cx+23*scale, cy-5*scale, smooth=True, splinesteps=20,
                         fill=white, outline=outline, width=1.8)
        c.create_oval(cx-24*scale, cy-22*scale, cx-10*scale, cy-7*scale,
                      fill=blue, outline=outline, width=1.4)
        c.create_oval(cx+10*scale, cy-22*scale, cx+24*scale, cy-7*scale,
                      fill=white, outline=outline, width=1.4)
        # 하치와레 느낌의 파란 머리 무늬와 둥근 앞머리
        cap = [cx-23*scale, cy-8*scale, cx-24*scale, cy-19*scale,
               cx-19*scale, cy-27*scale, cx-10*scale, cy-29*scale,
               cx-3*scale, cy-25*scale, cx+2*scale, cy-17*scale,
               cx+8*scale, cy-25*scale, cx+17*scale, cy-28*scale,
               cx+23*scale, cy-21*scale, cx+24*scale, cy-8*scale,
               cx+16*scale, cy-5*scale, cx+8*scale, cy-8*scale,
               cx+2*scale, cy-4*scale, cx-5*scale, cy-8*scale,
               cx-14*scale, cy-5*scale]
        c.create_polygon(cap, smooth=True, splinesteps=20, fill=blue, outline=outline, width=1.5)
        # 밝은 파란색 하이라이트
        c.create_arc(cx-18*scale, cy-25*scale, cx-3*scale, cy-14*scale,
                     start=25, extent=115, style="arc", outline=blue_light, width=2)
        # 분홍 볼
        c.create_oval(cx-19*scale, cy+1*scale, cx-11*scale, cy+7*scale,
                      fill="#f4b8c7", outline="")
        c.create_oval(cx+11*scale, cy+1*scale, cx+19*scale, cy+7*scale,
                      fill="#f4b8c7", outline="")
        if sleeping:
            c.create_arc(cx-12*scale, cy-5*scale, cx-5*scale, cy+1*scale,
                         start=190, extent=160, style="arc", outline=outline, width=1.7)
            c.create_arc(cx+5*scale, cy-5*scale, cx+12*scale, cy+1*scale,
                         start=190, extent=160, style="arc", outline=outline, width=1.7)
            c.create_text(cx+31, cy-27, text="z z", fill="#8a9bc8", font=("Arial", 9, "bold"))
        elif active == "cry":
            c.create_oval(cx-13*scale, cy-6*scale, cx-6*scale, cy+2*scale, fill=outline, outline="")
            c.create_oval(cx+6*scale, cy-6*scale, cx+13*scale, cy+2*scale, fill=outline, outline="")
            c.create_oval(cx-13*scale, cy+1*scale, cx-9*scale, cy+11*scale, fill="#83c7f2", outline="")
            c.create_oval(cx+9*scale, cy+1*scale, cx+13*scale, cy+11*scale, fill="#83c7f2", outline="")
        else:
            # 눈동자와 반짝임
            eye_y = cy-5*scale
            c.create_oval(cx-13*scale, eye_y-4*scale, cx-6*scale, eye_y+5*scale, fill=outline, outline="")
            c.create_oval(cx+6*scale, eye_y-4*scale, cx+13*scale, eye_y+5*scale, fill=outline, outline="")
            c.create_oval(cx-11*scale, eye_y-2*scale, cx-9*scale, eye_y+1*scale, fill="#ffffff", outline="")
            c.create_oval(cx+8*scale, eye_y-2*scale, cx+10*scale, eye_y+1*scale, fill="#ffffff", outline="")
        # 작은 코와 입 모양
        c.create_oval(cx-2*scale, cy+1*scale, cx+2*scale, cy+4*scale, fill="#5b4b55", outline="")
        if happy or active in ("eat", "play", "dance"):
            c.create_arc(cx-4*scale, cy+2*scale, cx+4*scale, cy+9*scale,
                         start=200, extent=140, style="arc", outline="#5b4b55", width=1.6)
            c.create_text(cx+31, cy-23, text="♥", fill="#e89bad", font=("Arial", 10, "bold"))
        elif active == "bow":
            c.create_arc(cx-4*scale, cy+2*scale, cx+4*scale, cy+7*scale,
                         start=20, extent=140, style="arc", outline="#5b4b55", width=1.4)
        else:
            c.create_arc(cx-3*scale, cy+3*scale, cx+3*scale, cy+7*scale,
                         start=200, extent=140, style="arc", outline="#5b4b55", width=1.3)
        # 행동별 효과
        if active == "dance":
            c.create_text(cx-34, cy-22, text="♪", fill="#e99bb7", font=("Arial", 13, "bold"))
            c.create_text(cx+35, cy-25, text="♫", fill="#77a9d8", font=("Arial", 12, "bold"))
        elif active == "run":
            c.create_line(cx-29, cy+6, cx-36, cy+3, fill=blue_light, width=2)
            c.create_line(cx-28, cy+12, cx-35, cy+12, fill=blue_light, width=2)
        elif active == "jump":
            c.create_text(cx+30, cy-31, text="✦", fill="#e9bd65", font=("Arial", 12, "bold"))
        elif active == "stretch":
            c.create_line(cx-19, cy+13, cx-27, cy+4, fill=white, width=4)
            c.create_line(cx+19, cy+13, cx+27, cy+4, fill=white, width=4)
        # 성장 장식: 높은 레벨에서는 왕관이 생깁니다.
        if level >= 3:
            c.create_text(cx-32, cy-29, text="✦", fill="#e9bd65", font=("Arial", 9, "bold"))
        if level >= 5:
            c.create_text(cx+33, cy-31, text="✦", fill="#e9bd65", font=("Arial", 10, "bold"))
        if level >= 10:
            c.create_oval(cx+18, cy-39, cx+25, cy-32, fill="#f3c4d7", outline="")
        if level >= 20:
            crown = [cx-10, cy-35, cx-12, cy-44, cx-5, cy-39, cx, cy-47,
                     cx+5, cy-39, cx+12, cy-44, cx+10, cy-35]
            c.create_polygon(crown, fill="#ffd66e", outline="#d5a83e", width=1.2)
        if self.data["hunger"] < 20 and not sleeping:
            c.create_text(cx-34, cy-27, text="…", fill="#b78b95", font=("Arial", 10, "bold"))

    def refresh(self):
        self.draw_pet()

    def tick(self):
        now = time.time()
        dt = max(0.01, min(0.1, now-self.last_tick)); self.last_tick = now
        self.data["age_seconds"] = self.data.get("age_seconds", 0) + dt
        self.data["hunger"] = clamp(self.data["hunger"] - 0.025*dt)
        self.data["happiness"] = clamp(self.data["happiness"] - 0.015*dt)
        self.data["energy"] = clamp(self.data["energy"] - 0.01*dt)
        x, y = self.root.winfo_x(), self.root.winfo_y()
        floor_y = self.taskbar_y()
        if self.physics:
            self.vy += 1.25
            y += int(self.vy)
            if y >= floor_y:
                y = floor_y
                self.physics = False
                self.vy = 0
                self.action, self.action_until = "land", now+0.35
                self.root.geometry(f"+{max(0,min(self.root.winfo_screenwidth()-W,x))}+{y}")
                self.root.after(350, self.stand_after_landing)
            else:
                self.root.geometry(f"+{max(0,min(self.root.winfo_screenwidth()-W,x))}+{y}")
        elif not self.drag_start:
            if self.menu_window and self.menu_window.winfo_exists():
                pass
            elif self.action in ("land", "falling", "held") and now < self.action_until:
                pass
            elif self.action == "sleep" and now < self.action_until:
                pass
            else:
                if self.action in ("sleep", "land", "falling", "held", "happy", "play", "eat", "stand") and now >= self.action_until:
                    self.action = "idle"
                # Walk autonomously along the top edge of the taskbar.
                if now >= self.next_turn and self.action in ("idle", "happy", "play", "eat"):
                    self.direction = random.choice([-1, 1])
                    self.walking = random.random() > 0.25
                    self.next_turn = now + random.uniform(1.5, 4.5)
                if self.walking and self.action == "idle":
                    x += int(self.direction * 1.8)
                    max_x = max(0, self.root.winfo_screenwidth()-W)
                    if x <= 0: x, self.direction = 0, 1
                    elif x >= max_x: x, self.direction = max_x, -1
                    y = floor_y
                    self.root.geometry(f"+{x}+{y}")
        if now - self.data.get("last_saved", 0) > 20: self.save_data()
        self.refresh()
        self.root.after(40, self.tick)

    def stand_after_landing(self):
        if not self.physics and not self.drag_start:
            self.action, self.action_until = "stand", time.time()+0.55
            self.walking = True
            self.next_turn = time.time()+0.8
            self.refresh()

    def close(self):
        self.save_data()
        try:
            if self.menu_window and self.menu_window.winfo_exists(): self.menu_window.destroy()
        except Exception: pass
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = DeskPet(root)
    root.mainloop()
