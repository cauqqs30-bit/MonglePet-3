import tkinter as tk
from tkinter import messagebox
import json, os, time, math, random
from pathlib import Path

APP_NAME = "몽글펫"
SAVE_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "MonglePet"
SAVE_FILE = SAVE_DIR / "save.json"
KEY = "#ff00ff"
W, H = 160, 150
PET_W, PET_H = 112, 120
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
        self.action_started = time.time()
        self.direction = random.choice([-1, 1])
        self.walking = True
        self.next_turn = time.time() + random.uniform(2.0, 5.0)
        self.last_tick = time.time()
        self.blink_until = 0
        self.menu = tk.Menu(root, tearoff=0, font=("맑은 고딕", 10))
        self.menu.add_command(label="🍙 밥 주기", command=self.feed)
        self.menu.add_command(label="🧸 놀아주기 (+코인)", command=self.play)
        self.menu.add_command(label="💤 침대에서 낮잠 자기", command=self.sleep_pet)
        self.menu.add_command(label="🏃 뛰기", command=lambda: self.do_action("run", 5.0))
        self.menu.add_command(label="🪑 앉기", command=lambda: self.do_action("sit", 4.0))
        self.menu.add_command(label="💃 춤추기", command=lambda: self.do_action("dance", 5.0))
        self.menu.add_command(label="🧘 기지개 켜기", command=lambda: self.do_action("stretch", 3.0))
        self.menu.add_command(label="🫶 쓰다듬기", command=lambda: self.do_action("pet", 3.0))
        self.menu.add_separator()
        self.menu.add_command(label="🎒 상태 확인", command=self.show_status)
        self.menu.add_command(label="🛍 간식 상점", command=self.open_shop)
        self.menu.add_separator()
        self.menu.add_command(label="💾 지금 저장", command=self.save_data)
        self.menu.add_command(label="✕ 종료", command=self.close)
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
        try: self.menu.tk_popup(e.x_root, e.y_root)
        finally:
            self.menu.grab_release()
            self.walking = True

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
        self.action, self.action_until = "eat", time.time()+3.0
        self.save_data(); self.refresh()

    def play(self):
        if self.data["energy"] < 12:
            messagebox.showinfo("조금 쉬자", "몽글이가 피곤해. 먼저 낮잠을 재워 줘.", parent=self.root); return
        self.data["happiness"] = clamp(self.data["happiness"] + 18)
        self.data["energy"] = clamp(self.data["energy"] - 10)
        self.data["hunger"] = clamp(self.data["hunger"] - 5)
        self.data["xp"] += 8; self.data["coins"] += 5
        self.action, self.action_until = "play", time.time()+3.5
        self.save_data(); self.refresh()

    def sleep_pet(self):
        self.data["energy"] = clamp(self.data["energy"] + 30)
        self.action_started = time.time()
        self.action, self.action_until = "sleep", self.action_started+12
        self.walking = False
        self.save_data(); self.refresh()

    def show_status(self):
        d = self.data
        msg = (f"몽글이 · {self.stage()} · Lv.{1+int(d['xp']//50)}\n\n"
               f"🍙 포만감  {int(d['hunger'])}%\n😊 행복    {int(d['happiness'])}%\n⚡ 기력    {int(d['energy'])}%\n\n"
               f"🪙 코인    {d['coins']}\n🍡 간식    {d['items'].get('간식',0)}개\n🧸 장난감  {d['items'].get('장난감',0)}개")
        messagebox.showinfo("몽글펫 상태", msg, parent=self.root)

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
        messagebox.showinfo("구매 완료", f"{item} 구매 완료!", parent=win)

    def do_action(self, action, duration=3.0):
        self.action = action
        self.action_started = time.time()
        self.action_until = self.action_started + duration
        self.walking = False
        if action in ("run", "dance", "play", "pet"):
            self.data["happiness"] = clamp(self.data["happiness"] + (5 if action != "pet" else 3))
        if action == "run":
            self.data["energy"] = clamp(self.data["energy"] - 4)
        self.save_data(); self.refresh()

    def draw_pet(self):
        c = self.canvas; c.delete("all")
        t = time.time(); a = self.action
        active = t < self.action_until
        if not active and a not in ("idle",): a = "idle"
        phase = t * (17 if a == "run" else 8)
        bob = math.sin(phase) * (5 if a in ("run", "dance", "play") else 1.8)
        cx = 80; floor = 130
        # Ground shadow and action-specific props
        c.create_oval(37, 126, 123, 139, fill="#e9e2e5", outline="")
        if a == "sleep":
            # 침대가 부드럽게 들어오고 몽글이가 천천히 몸을 낮춘 뒤 이불을 덮습니다.
            elapsed = max(0.0, t - self.action_started)
            enter = min(1.0, elapsed / 0.85)
            settle = min(1.0, max(0.0, (elapsed - 0.45) / 0.9))
            bed_y = 150 - 18 * enter
            c.create_oval(17, bed_y-48, 143, bed_y+12, fill="#b8d9f5", outline="#8ebbe3", width=3)
            c.create_oval(24, bed_y-43, 136, bed_y+5, fill="#d9edff", outline="#a8cfee", width=2)
            c.create_oval(28, bed_y-42, 132, bed_y-8, fill="#fff8f3", outline="#eadfe0", width=2)
            cat_y = 83 + 16 * settle + math.sin(t*2.2)*0.8
            self.draw_cat(c, 80, cat_y, 0.93, "sleep", t, True)
            blanket = min(1.0, max(0.0, (elapsed - 1.15) / 0.8))
            if blanket > 0:
                top = 122 - 19 * blanket
                c.create_oval(28, top, 132, 151, fill="#a9d2f3", outline="#86b6e3", width=2)
                c.create_arc(30, top+2, 130, 151, start=0, extent=180, style="arc", outline="#d9edff", width=3)
            if elapsed > 1.8:
                z_y = 45 + math.sin(t*2)*4
                c.create_text(124, z_y, text="Z", fill="#82a9d4", font=("맑은 고딕", 12, "bold"))
                c.create_text(140, z_y-15, text="z", fill="#82a9d4", font=("맑은 고딕", 9, "bold"))
            return
        if a == "eat":
            c.create_oval(103, 112, 145, 132, fill="#f5b7c8", outline="#d98ca3", width=2)
            c.create_oval(108, 113, 140, 124, fill="#ffe4a6", outline="#d9b879")
            for i in range(4): c.create_oval(111+i*7, 115+(i%2)*2, 115+i*7, 119+(i%2)*2, fill="#e99d69", outline="")
            self.draw_cat(c, 67, 103+bob*.2, 0.9, "eat", t, False)
            c.create_text(122, 91, text="냠냠", fill="#e49a76", font=("맑은 고딕", 9, "bold"))
            return
        if a == "sit":
            self.draw_cat(c, cx, 111, 1.0, "sit", t, False); return
        if a == "stretch":
            self.draw_cat(c, cx, 111, 1.0, "stretch", t, False); return
        if a == "run":
            # speed streaks + fast alternating stride
            for i in range(3): c.create_line(8+i*8, 87+i*10, 32+i*8, 87+i*10, fill="#b9dff7", width=3, capstyle="round")
            self.draw_cat(c, cx, 105+bob, 1.0, "run", t, False)
            return
        if a == "dance":
            self.draw_cat(c, cx, 106+bob, 1.0, "dance", t, False)
            c.create_text(24, 62, text="♪", fill="#e9a7c2", font=("Arial", 18, "bold")); c.create_text(135, 53, text="♫", fill="#8ebbe3", font=("Arial", 17, "bold")); return
        if a == "play":
            c.create_oval(117+math.sin(t*5)*8, 110, 139+math.sin(t*5)*8, 132, fill="#8cc8f0", outline="#6da9d7", width=2)
            self.draw_cat(c, cx, 106+bob, 1.0, "play", t, False); return
        if a == "pet":
            c.create_oval(115, 24+math.sin(t*8)*3, 146, 48+math.sin(t*8)*3, fill="#ffe0c9", outline="#e9bda6", width=2)
            c.create_line(127, 46, 120, 57, fill="#e9bda6", width=4)
            c.create_text(30, 47, text="♥", fill="#f29ab0", font=("Arial", 16, "bold"))
        self.draw_cat(c, cx, 107+bob, 1.0, "idle", t, False)
        if self.data["hunger"] < 20: c.create_text(35, 52, text="…", fill="#b78b95", font=("Arial", 14, "bold"))

    def draw_cat(self, c, cx, cy, scale, pose, t, on_bed):
        # Original white kitten: rounded silhouette, pink ears/cheeks, blue collar and bell.
        s=scale; outline="#d8cfd0"; fur="#fffdfb"
        lean = 8*math.sin(t*14) if pose in ("run", "dance") else 0
        # tail, animated separately
        tail_y = math.sin(t*5)*5
        c.create_oval(cx+24*s, cy+3*s+tail_y, cx+43*s, cy+27*s+tail_y, fill=fur, outline=outline, width=2)
        # body
        if pose == "sleep":
            c.create_oval(cx-39*s, cy-6*s, cx+39*s, cy+31*s, fill=fur, outline=outline, width=2)
            c.create_oval(cx-32*s, cy-19*s, cx+30*s, cy+19*s, fill=fur, outline=outline, width=2)
            c.create_polygon(cx-28*s,cy-28*s,cx-24*s,cy-52*s,cx-5*s,cy-32*s, fill=fur, outline=outline, width=2)
            c.create_polygon(cx+8*s,cy-32*s,cx+29*s,cy-52*s,cx+32*s,cy-23*s, fill=fur, outline=outline, width=2)
            c.create_line(cx-13*s,cy-4*s,cx-5*s,cy-2*s,fill="#55474b",width=2)
            c.create_line(cx+5*s,cy-2*s,cx+13*s,cy-4*s,fill="#55474b",width=2)
            c.create_oval(cx-19*s,cy+2*s,cx-9*s,cy+9*s,fill="#f5becb",outline="")
            c.create_oval(cx+9*s,cy+2*s,cx+19*s,cy+9*s,fill="#f5becb",outline="")
            return
        # feet with alternating movement for running
        stride = math.sin(t*19)*10 if pose == "run" else (math.sin(t*9)*4 if pose=="dance" else 0)
        if pose == "stretch":
            c.create_oval(cx-40*s,cy+10*s,cx-7*s,cy+23*s,fill=fur,outline=outline,width=2)
            c.create_oval(cx+7*s,cy+10*s,cx+40*s,cy+23*s,fill=fur,outline=outline,width=2)
        elif pose == "run":
            lift_a = max(0, math.sin(t*19))*8
            lift_b = max(0, -math.sin(t*19))*8
            c.create_oval(cx-25*s-stride*.55,cy+34*s-lift_a,cx-3*s-stride*.55,cy+43*s-lift_a,fill=fur,outline=outline,width=2)
            c.create_oval(cx+3*s+stride*.55,cy+34*s-lift_b,cx+25*s+stride*.55,cy+43*s-lift_b,fill=fur,outline=outline,width=2)
        else:
            c.create_oval(cx-24*s-stride,cy+34*s,cx-2*s-stride,cy+43*s,fill=fur,outline=outline,width=2)
            c.create_oval(cx+3*s+stride,cy+34*s,cx+25*s+stride,cy+43*s,fill=fur,outline=outline,width=2)
        c.create_oval(cx-29*s,cy+1*s,cx+29*s,cy+39*s,fill=fur,outline=outline,width=2)
        if pose == "run":
            arm = math.sin(t*19)*7
            c.create_oval(cx-34*s, cy+12*s+arm, cx-21*s, cy+28*s+arm, fill=fur, outline=outline, width=2)
            c.create_oval(cx+21*s, cy+12*s-arm, cx+34*s, cy+28*s-arm, fill=fur, outline=outline, width=2)
        # ears
        c.create_polygon(cx-30*s,cy-22*s,cx-27*s,cy-53*s,cx-5*s,cy-31*s,fill=fur,outline=outline,width=2)
        c.create_polygon(cx+5*s,cy-31*s,cx+27*s,cy-53*s,cx+31*s,cy-20*s,fill=fur,outline=outline,width=2)
        c.create_polygon(cx-24*s,cy-31*s,cx-26*s,cy-45*s,cx-14*s,cy-32*s,fill="#f7c8d0",outline="")
        c.create_polygon(cx+14*s,cy-32*s,cx+25*s,cy-45*s,cx+24*s,cy-29*s,fill="#f7c8d0",outline="")
        # head
        c.create_oval(cx-39*s+lean,cy-36*s,cx+39*s+lean,cy+29*s,fill=fur,outline=outline,width=2)
        # cheeks and face
        c.create_oval(cx-30*s+lean,cy+2*s,cx-19*s+lean,cy+12*s,fill="#f6c1cc",outline="")
        c.create_oval(cx+19*s+lean,cy+2*s,cx+30*s+lean,cy+12*s,fill="#f6c1cc",outline="")
        if pose == "sleep":
            pass
        elif pose == "eat":
            c.create_oval(cx-13*s,cy-8*s,cx-7*s,cy+1*s,fill="#42383b",outline="")
            c.create_oval(cx+7*s,cy-8*s,cx+13*s,cy+1*s,fill="#42383b",outline="")
            c.create_oval(cx-4*s,cy+4*s,cx+4*s,cy+12*s,fill="#bd778b",outline="")
        else:
            blink = (int(t*2.2)%5==0 and (t*2.2)%1>0.82)
            if blink:
                c.create_line(cx-16*s,cy-5*s,cx-8*s,cy-5*s,fill="#42383b",width=2)
                c.create_line(cx+8*s,cy-5*s,cx+16*s,cy-5*s,fill="#42383b",width=2)
            else:
                c.create_oval(cx-16*s,cy-10*s,cx-8*s,cy+3*s,fill="#42383b",outline="")
                c.create_oval(cx+8*s,cy-10*s,cx+16*s,cy+3*s,fill="#42383b",outline="")
                c.create_oval(cx-13*s,cy-8*s,cx-10*s,cy-4*s,fill="white",outline="")
                c.create_oval(cx+11*s,cy-8*s,cx+14*s,cy-4*s,fill="white",outline="")
            c.create_oval(cx-3*s,cy+5*s,cx+3*s,cy+9*s,fill="#e99baa",outline="")
            c.create_arc(cx-7*s,cy+6*s,cx+7*s,cy+17*s,start=200,extent=140,style="arc",outline="#59494d",width=2)
        # blue collar and golden bell
        c.create_arc(cx-25*s,cy+17*s,cx+25*s,cy+39*s,start=190,extent=160,style="arc",outline="#91c9ee",width=5)
        c.create_oval(cx-5*s,cy+29*s,cx+5*s,cy+39*s,fill="#f4ca68",outline="#d7a94a",width=1)

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
            if self.action == "run" and now < self.action_until:
                x += int(self.direction * 8)
                max_x = max(0, self.root.winfo_screenwidth()-W)
                if x <= 0: x, self.direction = 0, 1
                elif x >= max_x: x, self.direction = max_x, -1
                self.root.geometry(f"+{x}+{floor_y}")
            if self.action in ("land", "falling", "held") and now < self.action_until:
                pass
            elif self.action == "sleep" and now < self.action_until:
                pass
            else:
                if self.action in ("sleep", "land", "falling", "held", "happy", "play", "eat", "stand", "run", "sit", "dance", "stretch", "pet") and now >= self.action_until:
                    self.action = "idle"
                # Walk autonomously along the top edge of the taskbar.
                if now >= self.next_turn and self.action in ("idle", "happy", "play", "eat"):
                    self.direction = random.choice([-1, 1])
                    self.walking = random.random() > 0.25
                    self.next_turn = now + random.uniform(1.5, 4.5)
                if self.walking and self.action == "idle":
                    x += int(self.direction * 2.0)
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
        self.save_data(); self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = DeskPet(root)
    root.mainloop()
