import flet as ft
import cv2
import numpy as np
import threading
import os
import math
import random
import subprocess
from datetime import datetime, timedelta
from PIL import Image, ImageDraw

# ================= 核心 1：假想风季生成器 (纯逻辑) =================
def generate_fake_season(start_date, end_date):
    """随机虚构台风季，只生成逻辑数据，不包含任何视觉特效"""
    active_intervals = []
    fake_storms = []
    current_date = start_date
    
    while current_date < end_date:
        if random.random() > 0.4: 
            duration_days = random.randint(7, 15)
            storm_start = current_date + timedelta(days=random.randint(1, 10))
            storm_end = storm_start + timedelta(days=duration_days)
            
            if storm_end < end_date:
                active_intervals.append((storm_start, storm_end))
                fake_storms.append({
                    "id": f"{random.randint(1, 30):02d}W",
                    "name": f"Fake_{random.randint(1, 99)}",
                    "start": storm_start, 
                    "end": storm_end,
                    "peak_wind": random.randint(80, 170)
                })
        current_date += timedelta(days=30)
    return active_intervals, fake_storms

# ================= 核心 2：非线性时间映射器 (空档期快进) =================
class TimeMapper:
    def __init__(self, start_time, end_time, active_intervals, fast_forward_hours=24):
        self.start_time = start_time
        self.end_time = end_time
        self.active_intervals = active_intervals
        self.fast_forward = fast_forward_hours
        self.frame_times = []
        self._build()

    def _build(self):
        curr = self.start_time
        while curr < self.end_time:
            is_active = any(s <= curr <= e for s, e in self.active_intervals)
            self.frame_times.append(curr)
            
            if is_active:
                curr += timedelta(hours=1) # 有台风，原速
            else:
                curr += timedelta(hours=self.fast_forward) # 无台风，时间轴快进

    def get_time(self, frame_idx):
        if frame_idx >= len(self.frame_times): return self.end_time
        return self.frame_times[frame_idx]

    def total_frames(self):
        return len(self.frame_times)

# ================= 核心 3：总结条状态机 =================
class SummaryCard:
    def __init__(self, storm_data, slot_index, trigger_frame, width):
        self.storm = storm_data
        self.slot = slot_index
        self.start_frame = trigger_frame
        
        self.card_w, self.card_h = 580, 150
        self.target_x = width - self.card_w - 30 
        self.hidden_x = width 
        self.y = 50 + self.slot * (self.card_h + 20)
        
        self.state = "sliding_in" 
        self.timer = 0
        self.current_x = self.hidden_x

    def update(self, frame_idx):
        t = frame_idx - self.start_frame
        if t < 0: return False 
        
        if self.state == "sliding_in":
            self.timer += 1
            progress = min(1.0, self.timer / 30.0)
            ease = 1 - pow(1 - progress, 3)
            self.current_x = int(self.hidden_x - (self.hidden_x - self.target_x) * ease)
            if progress >= 1.0: self.state = "staying"; self.timer = 0
        elif self.state == "staying":
            self.timer += 1
            if self.timer > 90: self.state = "sliding_out"; self.timer = 0
        elif self.state == "sliding_out":
            self.timer += 1
            progress = min(1.0, self.timer / 30.0)
            ease = 1 - pow(1 - progress, 3)
            self.current_x = int(self.target_x + (self.hidden_x - self.target_x) * ease)
            if progress >= 1.0: self.state = "gone"
        return self.state != "gone"

    def draw(self, draw):
        if self.state == "gone": return
        x, y = self.current_x, self.y
        draw.rectangle([(x, y), (x + self.card_w, y + self.card_h)], fill=(0, 0, 0, 220))
        draw.text((x + 20, y + 20), f"ID: {self.storm['id']}", fill=(255, 255, 255))
        draw.text((x + 20, y + 50), f"Name: {self.storm['name']}", fill=(255, 255, 255))
        draw.text((x + 20, y + 80), f"Peak: {self.storm['peak_wind']} kt", fill=(255, 255, 0))

# ================= 核心 4：纯净渲染主循环 =================
def render_logic(bg_path, icon_path, update_ui):
    try:
        update_ui("启动假想风季引擎 (无额外视觉特效)...", "orange")
        
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 12, 31)
        active_intervals, storms = generate_fake_season(start_date, end_date)
        
        if not storms:
            update_ui("❌ 随机生成失败，今年没有台风！", "red")
            return

        mapper = TimeMapper(start_date, end_date, active_intervals)
        total_frames = mapper.total_frames()
        update_ui(f"时间轴构建完成，共 {total_frames} 帧（含快进空窗期）。", "green")

        bg = cv2.imread(bg_path)
        if bg is None: return
        bg = cv2.resize(bg, (1080, 1920))
        h, w = bg.shape[:2]

        out_path = "/storage/emulated/0/Download/fake_season_pure.mp4"
        command = [
            'ffmpeg', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24',
            '-s', f'{w}x{h}', '-r', '30', '-i', '-', '-an', '-c:v', 'libx264', 
            '-preset', 'fast', '-crf', '20', '-pix_fmt', 'yuv420p', out_path
        ]
        writer = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        cap_icon = cv2.VideoCapture(icon_path)

        cards = []
        slot_counter = 0
        for i, storm in enumerate(storms):
            end_frame = next((idx for idx, t in enumerate(mapper.frame_times) if t >= storm['end']), total_frames - 1)
            trigger = max(0, end_frame - 30)
            cards.append(SummaryCard(storm, slot_counter % 3, trigger, w))
            slot_counter += 1

        for frame_idx in range(total_frames):
            current_time = mapper.get_time(frame_idx)
            frame = bg.copy()

            for i, storm in enumerate(storms):
                if storm['start'] <= current_time <= storm['end']:
                    progress = (current_time - storm['start']).total_seconds() / (storm['end'] - storm['start']).total_seconds()
                    sx = int(200 + progress * 600)
                    sy = int(1600 - progress * 1000)
                    
                    # 纯粹画个路径点，没有花里胡哨的变色
                    cv2.circle(frame, (sx, sy), 20, (0, 0, 255), -1)
                    
                    if cap_icon.isOpened():
                        ret, icon = cap_icon.read()
                        if not ret:
                            cap_icon.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            ret, icon = cap_icon.read()
                        if ret:
                            icon = cv2.resize(icon, (80, 80))
                            top, left = max(0, sy-40), max(0, sx-40)
                            bot, right = min(h, top+80), min(w, left+80)
                            if top < bot and left < right:
                                ic = icon[0:bot-top, 0:right-left]
                                roi = frame[top:bot, left:right]
                                frame[top:bot, left:right] = cv2.addWeighted(roi, 0.5, ic, 0.5, 0)

            pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            draw = ImageDraw.Draw(pil_img, 'RGBA')
            
            # 左下角时间轴
            draw.rectangle([(20, h - 100), (600, h - 40)], fill=(0, 0, 0, 200))
            draw.text((30, h - 85), f"UTC: {current_time.strftime('%Y-%m-%d %H:%M')}", fill=(255, 255, 255))

            # 右下角 ACE
            draw.rectangle([(w-380, h - 160), (w-20, h - 40)], fill=(0, 0, 0, 200))
            fake_ace = (frame_idx / total_frames) * 80.0
            hist_avg = (frame_idx / total_frames) * 50.0
            draw.text((w-360, h - 140), f"ACE: {fake_ace:.2f}", fill=(255, 255, 0))
            draw.text((w-360, h - 110), f"Hist: {hist_avg:.2f}", fill=(255, 255, 255))
            
            chart_y = h - 60
            chart_w = 320
            hist_y = chart_y - (hist_avg / 100.0) * 40
            ace_y = chart_y - (fake_ace / 100.0) * 40
            draw.line([(w-360, chart_y), (w-360 + chart_w, hist_y)], fill=(255, 255, 255), width=1)
            draw.line([(w-360, chart_y), (w-360 + chart_w, ace_y)], fill=(255, 255, 0), width=3)

            for card in cards:
                if card.update(frame_idx):
                    card.draw(draw)

            frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            writer.stdin.write(frame.tobytes())
            
            if frame_idx % 100 == 0:
                update_ui(f"渲染进度: {frame_idx}/{total_frames}", "orange")

        cap_icon.release()
        writer.stdin.close()
        writer.wait()
        update_ui(f"✅ 纯净版渲染完成！已保存至 Download。", "green")

    except Exception as e:
        update_ui(f"❌ 渲染失败: {e}", "red")

# ================= Flet 界面 =================
def main(page: ft.Page):
    page.title = "假想台风季模拟 (纯净版)"
    page.theme_mode = ft.ThemeMode.DARK
    log_box = ft.TextField(multiline=True, read_only=True, height=150)
    status_text = ft.Text("请选择底图和图标", color="green")

    paths = {"bg": "", "icon": ""}
    file_picker = ft.FilePicker()
    page.overlay.append(file_picker)

    def update_ui(msg, color):
        log_box.value += msg + "\n"
        status_text.value = msg
        status_text.color = color
        page.update()

    async def pick_bg(e):
        res = await file_picker.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.IMAGE)
        if res: paths["bg"] = res[0].path; update_ui(f"底图: {res[0].name}", "white")

    async def pick_icon(e):
        res = await file_picker.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.VIDEO)
        if res: paths["icon"] = res[0].path; update_ui(f"图标: {res[0].name}", "white")

    def start_sim(e):
        if not paths["bg"] or not paths["icon"]:
            update_ui("❌ 请把底图和图标全选上！", "red")
            return
        threading.Thread(target=render_logic, args=(paths["bg"], paths["icon"], update_ui)).start()

    page.add(
        ft.Container(
            content=ft.Column([
                ft.Text("假想风季 + 物理推演 (纯净无特效版)", size=22, weight=ft.FontWeight.BOLD),
                ft.Text("没有副高云雾，没有变色魔法，只有台风与时间轴", size=12, color="grey"),
                ft.Divider(),
                ft.Row([
                    ft.Button("1. 选择底图", on_click=pick_bg),
                    ft.Button("2. 选择动态图标", on_click=pick_icon),
                ]),
                ft.Button("▶ 启动纯净模拟", on_click=start_sim, bgcolor="orange", color="white", width=300),
                status_text,
                log_box
            ]),
            padding=20
        )
    )

if __name__ == "__main__":
    ft.run(main)
