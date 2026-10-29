import tkinter as tk
from tkinter import messagebox
import json, os, time, math, random
from pathlib import Path

APP_NAME = "몽글펫"
SAVE_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "MonglePet"
SAVE_FILE = SAVE_DIR / "save.json"
KEY = "#ff00ff"
W, H = 92, 86
PET_W, PET_H = 64, 68
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
        self.menu = tk.Menu(root, tearoff=0, font=("맑은 고딕", 10))
        self.menu.add_command(label="🍙 밥 주기", command=self.feed)
        self.menu.add_command(label="🧸 놀아주기 (+코인)", command=self.play)
        self.menu.add_separator()
        self.menu.add_command(label="😭 울어버리기", command=lambda: self.perform_action("cry", 2.4))
        self.menu.add_command(label="🤸 잠 깬 뒤 체조하기", command=lambda: self.perform_action("stretch", 3.2))
        self.menu.add_command(label="💃 파스타 댄스", command=lambda: self.perform_action("dance", 4.0))
        self.menu.add_command(label="🏃 신나게 달리기", command=lambda: self.perform_action("run", 2.8))
        self.menu.add_command(label="🙇 꾸벅 인사하기", command=lambda: self.perform_action("bow", 1.8))
        self.menu.add_command(label="🐇 폴짝 뛰기", command=lambda: self.perform_action("jump", 1.8))
        self.menu.add_command(label="💤 낮잠 자기", command=self.sleep_pet)
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
        self.perform_action("sleep", 3.5, save=False)
        self.save_data(); self.refresh()

    def perform_action(self, action, duration=2.5, save=True):
        """Play a short cute emote without opening a large window."""
        self.walking = False
        self.action = action
        self.action_until = time.time() + duration
        if action in ("stretch", "dance", "run", "bow", "jump"):
            self.data["happiness"] = clamp(self.data["happiness"] + (5 if action == "dance" else 3))
        if action in ("jump", "run", "dance"):
            self.data["energy"] = clamp(self.data["energy"] - (4 if action == "dance" else 3 if action == "run" else 2))
        if save:
            self.save_data()
        self.refresh()

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

    def draw_pet(self):
        c = self.canvas; c.delete("all")
        t = time.time()
        active = t < self.action_until
        sleeping = self.action == "sleep" and active
        crying = self.action == "cry" and active
        laughing = self.action == "laugh" and active
        stretching = self.action == "stretch" and active
        dancing = self.action == "dance" and active
        running = self.action == "run" and active
        bowing = self.action == "bow" and active
        jumping = self.action == "jump" and active
        happy = self.action in ("happy", "play", "eat", "stand", "dance", "stretch", "run", "jump") and active
        falling = self.action in ("falling", "held")
        bob = math.sin(t*7)*1.5 if self.walking and not sleeping else (0 if falling else math.sin(t*3)*1.0)
        if jumping:
            bob -= abs(math.sin((t % 0.6) / 0.6 * math.pi)) * 15
        if dancing:
            bob += math.sin(t*16)*3
        if stretching:
            bob -= abs(math.sin((t % 1.0) / 1.0 * math.pi))*3
        if running:
            bob += abs(math.sin(t*22))*2
        squish = 0.72 if self.action == "land" and active else (0.82 if falling else 1.0)
        level = 1 + int(self.data.get("xp", 0)//50)
        scale = 0.88 + min(0.10, max(0, level-1)*0.006)
        cx, cy = W//2, 39 + bob
        if falling: cy += 4
        if bowing: cy += abs(math.sin((t % 0.9) / 0.9 * math.pi))*5
        # tiny shadow and body, sized to fit a compact transparent window
        c.create_oval(cx-22, 73, cx+22, 78, fill="#e7dfe2", outline="")
        c.create_oval(cx-19*scale, cy+4*scale, cx+19*scale, cy+29*scale*squish, fill="#fffdfb", outline="#d8cfd0", width=1)
        # ears
        c.create_oval(cx-14*scale, cy-25*scale, cx-6*scale, cy-10*scale, fill="#fffdfb", outline="#d8cfd0", width=1)
        c.create_oval(cx+6*scale, cy-25*scale, cx+14*scale, cy-10*scale, fill="#fffdfb", outline="#d8cfd0", width=1)
        c.create_oval(cx-12*scale, cy-21*scale, cx-8*scale, cy-12*scale, fill="#f5dce2", outline="")
        c.create_oval(cx+8*scale, cy-21*scale, cx+12*scale, cy-12*scale, fill="#f5dce2", outline="")
        # head
        c.create_oval(cx-22*scale, cy-20*scale, cx+22*scale, cy+17*scale, fill="#fffdfb", outline="#d8cfd0", width=1)
        c.create_oval(cx-16*scale, cy-1*scale, cx-9*scale, cy+4*scale, fill="#f4b9c7", outline="")
        c.create_oval(cx+9*scale, cy-1*scale, cx+16*scale, cy+4*scale, fill="#f4b9c7", outline="")
        if sleeping:
            c.create_line(cx-11*scale, cy-5*scale, cx-7*scale, cy-3*scale, fill="#51454a", width=1)
            c.create_line(cx+7*scale, cy-3*scale, cx+11*scale, cy-5*scale, fill="#51454a", width=1)
            c.create_text(cx+23, cy-20, text="z", fill="#9b8dc6", font=("Arial", 9, "bold"))
        elif stretching:
            c.create_arc(cx-12*scale, cy-9*scale, cx-5*scale, cy-2*scale, start=195, extent=150, style="arc", outline="#40363b", width=1.5)
            c.create_arc(cx+5*scale, cy-9*scale, cx+12*scale, cy-2*scale, start=195, extent=150, style="arc", outline="#40363b", width=1.5)
        elif laughing or dancing:
            c.create_arc(cx-12*scale, cy-7*scale, cx-5*scale, cy-1*scale, start=190, extent=160, style="arc", outline="#40363b", width=1.5)
            c.create_arc(cx+5*scale, cy-7*scale, cx+12*scale, cy-1*scale, start=190, extent=160, style="arc", outline="#40363b", width=1.5)
        else:
            # tiny dot eyes
            c.create_oval(cx-10*scale, cy-7*scale, cx-7*scale, cy-1*scale, fill="#40363b", outline="")
            c.create_oval(cx+7*scale, cy-7*scale, cx+10*scale, cy-1*scale, fill="#40363b", outline="")
        if happy:
            c.create_oval(cx-2*scale, cy+1*scale, cx+2*scale, cy+5*scale, fill="#a56e7a", outline="")
            emote = "♪" if dancing else "쭉!" if stretching else "슝!" if running else "♥"
            c.create_text(cx+25, cy-17, text=emote, fill="#e89bad", font=("맑은 고딕", 8, "bold"))
        elif crying:
            c.create_arc(cx-12*scale, cy-8*scale, cx-5*scale, cy-1*scale, start=15, extent=150, style="arc", outline="#40363b", width=1.5)
            c.create_arc(cx+5*scale, cy-8*scale, cx+12*scale, cy-1*scale, start=15, extent=150, style="arc", outline="#40363b", width=1.5)
            c.create_oval(cx-11*scale, cy+1*scale, cx-7*scale, cy+8*scale, fill="#83c9f4", outline="")
            c.create_oval(cx+7*scale, cy+1*scale, cx+11*scale, cy+8*scale, fill="#83c9f4", outline="")
            c.create_text(cx+24, cy-17, text="흑흑", fill="#78b9e7", font=("맑은 고딕", 7, "bold"))
        else:
            c.create_arc(cx-3*scale, cy+1*scale, cx+3*scale, cy+5*scale, start=200, extent=140, style="arc", outline="#6b555c", width=1)
        if stretching:
            # Arms reach upward during the wake-up stretch.
            c.create_line(cx-14, cy+9, cx-20, cy-5, fill="#fffdfb", width=4, capstyle="round")
            c.create_line(cx+14, cy+9, cx+20, cy-5, fill="#fffdfb", width=4, capstyle="round")
            c.create_text(cx-24, cy-18, text="✦", fill="#e9bd65", font=("Arial", 9, "bold"))
        if dancing:
            # Tiny swinging arms and musical notes for the pasta-dance-inspired emote.
            sway = math.sin(t*16)*5
            c.create_line(cx-14, cy+8, cx-21, cy+3+sway, fill="#fffdfb", width=4, capstyle="round")
            c.create_line(cx+14, cy+8, cx+21, cy+3-sway, fill="#fffdfb", width=4, capstyle="round")
            c.create_text(cx-25, cy-18, text="♪", fill="#e9bd65", font=("Arial", 9, "bold"))
            c.create_text(cx+25, cy-27, text="♫", fill="#e89bad", font=("Arial", 9, "bold"))
        if running:
            c.create_text(cx-25, cy-18, text="슝", fill="#e9bd65", font=("맑은 고딕", 8, "bold"))
            c.create_line(cx-25, cy+12, cx-19, cy+12, fill="#d8cfd0", width=1)
        if bowing:
            c.create_text(cx+25, cy-18, text="꾸벅", fill="#e89bad", font=("맑은 고딕", 7, "bold"))
        if laughing:
            c.create_text(cx-25, cy-18, text="♪", fill="#e9bd65", font=("Arial", 9, "bold"))
        # feet; tucked in during fall, spread when standing
        foot_y = cy+25*scale*squish
        foot_spread = 8 if falling else 11
        c.create_oval(cx-foot_spread-3, foot_y-2, cx-foot_spread+4, foot_y+3, fill="#fffdfb", outline="#d8cfd0", width=1)
        c.create_oval(cx+foot_spread-4, foot_y-2, cx+foot_spread+3, foot_y+3, fill="#fffdfb", outline="#d8cfd0", width=1)
        if level >= 5: c.create_text(cx, cy-29, text="✦", fill="#e9bd65", font=("Arial", 9, "bold"))
        if self.data["hunger"] < 20 and not sleeping: c.create_text(cx-26, cy-20, text="…", fill="#b78b95", font=("Arial", 10, "bold"))

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
                x += int(self.direction * 5.5)
                max_x = max(0, self.root.winfo_screenwidth()-W)
                if x <= 0: x, self.direction = 0, 1
                elif x >= max_x: x, self.direction = max_x, -1
                self.root.geometry(f"+{x}+{floor_y}")
            if self.action in ("land", "falling", "held") and now < self.action_until:
                pass
            elif self.action == "sleep" and now < self.action_until:
                pass
            else:
                if self.action in ("sleep", "land", "falling", "held", "happy", "play", "eat", "stand", "cry", "laugh", "stretch", "dance", "run", "bow", "jump") and now >= self.action_until:
                    self.action = "idle"
                    self.walking = True
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
        self.save_data(); self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = DeskPet(root)
    root.mainloop()
