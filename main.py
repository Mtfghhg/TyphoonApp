import flet as ft
import cv2
import numpy as np
import threading
import os
import math
import subprocess
from datetime import datetime, timedelta
from PIL import Image, ImageDraw

# ================= 核心 1：性质与风速整合判定（WV与DB同级） =================
def get_icon_key(nature, vmax):
    nature = nature.upper()
    
    # 1. 绝对变性优先 (EX温带, SS副热带)
    if nature in ["EX", "SS", "SD"]: return nature
    if nature == "MD": return "MD"
    
    # 2. 未成型系统 (热带波WV、低压LO、扰动DB 全部同级，按风速走)
    # 风速小于 25kt 统一归为 DB 级别
    if vmax < 25: 
        return "DB"
    elif vmax < 34: 
        return "TD"
    elif vmax < 64: 
        return "TS"
    elif vmax < 83: 
        return "C1"
    elif vmax < 96: 
        return "C2"
    elif vmax < 113: 
        return "C3"
    elif vmax < 137: 
        return "C4"
    elif vmax < 170: 
        return "C5"
    else: 
        return "C6"

# ================= 核心 2：B-deck 解析与“高斯平滑演算” =================
def parse_and_smooth_bdeck(filepath, target_peak_wind):
    records = []
    storm_name = "Unknown"
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if line.startswith('#') or not line.strip(): continue
                parts = line.split(',')
                if len(parts) < 11: continue
                try:
                    if len(parts) > 27 and parts[27].strip():
                        storm_name = parts[27].strip()
                    
                    t = datetime.strptime(parts[2].strip(), '%Y%m%d%H')
                    lat = float(parts[6].strip()[:-1]) / 10.0
                    if parts[6].strip()[-1] == 'S': lat = -lat
                    lon = float(parts[7].strip()[:-1]) / 10.0
                    if parts[7].strip()[-1] == 'W': lon = 360 - lon
                    vmax = int(parts[8].strip())
                    
                    nature = parts[10].strip() if len(parts) > 10 else "TC"
                    if not nature: nature = "TC"
                    
                    records.append({'time': t, 'lat': lat, 'lon': lon, 'jtc_vmax': vmax, 'nature': nature, 'name': storm_name})
                except: continue
    except Exception as e:
        print(f"B-deck read error: {e}")
    
    if not records: return []
    
    # ====== 高斯平滑拉伸核心算法 ======
    max_jtc = max(r['jtc_vmax'] for r in records)
    peak_idx = next(i for i, r in enumerate(records) if r['jtc_vmax'] == max_jtc)
    
    delta_v = target_peak_wind - max_jtc
    sigma = max(5, len(records) / 6.0) 
    
    for i, r in enumerate(records):
        dist = i - peak_idx
        weight = math.exp(-(dist ** 2) / (2 * (sigma ** 2)))
        boost = delta_v * weight
        r['fused_vmax'] = int(max(0, r['jtc_vmax'] + boost))
        
    return sorted(records, key=lambda x: x['time'])

# ================= 核心 3：非线性时间映射器 =================
class TimeMapper:
    def __init__(self, start_time, end_time, active_intervals, fast_forward_hours=24):
        self.frame_times = []
        curr = start_time
        while curr < end_time:
            is_active = any(s <= curr <= e for s, e in active_intervals)
            self.frame_times.append(curr)
            curr += timedelta(hours=1) if is_active else timedelta(hours=fast_forward_hours)
    def get_time(self, frame_idx):
        return self.frame_times[frame_idx] if frame_idx < len(self.frame_times) else self.frame_times[-1]

# ================= 核心 4：智能素材库 (完全兼容你的命名) =================
class MediaLibrary:
    def __init__(self, folder_path):
        self.icon_paths = {}      
        self.summary_paths = {}   
        self.month_paths = {}     
        self.ace_bg = None
        self.map_bg = None
        
        self.active_icon_key = None
        self.icon_cap = None
        self.active_timeline_month = -1
        self.timeline_cap = None

        if not os.path.exists(folder_path): return

        for f in os.listdir(folder_path):
            f_lower = f.lower()
            path = os.path.join(folder_path, f)
            f_upper = f.upper()

            if "wpac" in f_lower and f_lower.endswith(".png"): self.map_bg = cv2.imread(path)
            elif "ace_gui" in f_lower and f_lower.endswith(".png"): self.ace_bg = cv2.imread(path)
            elif f_lower.endswith(".mp4"):
                # 月份时间轴
                months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
                for i, m in enumerate(months):
                    if m in f_upper and "summary" not in f_lower:
                        self.month_paths[i+1] = path
                        break
                
                # 提取台风图标池
                if "SUMMARY" not in f_upper:
                    if "N-DB-AWV" in f_upper:
                        self.icon_paths["WV"] = path # 专门的波状扰动
                    elif "N-DB-AL" in f_upper:
                        self.icon_paths["LO"] = path # 专门的低压扰动
                    elif "N-DB-" in f_upper:
                        self.icon_paths["DB"] = path # 通用扰动
                    elif "N-TD-" in f_upper or "N-TC-" in f_upper or "N-EX-" in f_upper:
                        # 提取 C1, TS, EX 等后缀
                        cat = f_upper.replace(".MP4", "").split("-")[-1]
                        self.icon_paths[cat] = path
                
                # 提取总结条后缀
                elif "SUMMARY-N-TC-" in f_upper:
                    cat = f_upper.replace(".MP4", "").split("SUMMARY-N-TC-")[-1]
                    self.summary_paths[cat] = path

    def get_icon_cap(self, key, nature=""):
        nature = nature.upper()
        cache_key = f"{key}_{nature}"
        if self.active_icon_key == cache_key and self.icon_cap: 
            return self.icon_cap
            
        if self.icon_cap: self.icon_cap.release(); self.icon_cap = None
            
        # 核心：如果都归类到了 DB 级别，优先根据性质找细分视频
        if key == "DB":
            if nature == "WV" and "WV" in self.icon_paths:
                self.icon_cap = cv2.VideoCapture(self.icon_paths["WV"])
            elif nature == "LO" and "LO" in self.icon_paths:
                self.icon_cap = cv2.VideoCapture(self.icon_paths["LO"])
            elif "DB" in self.icon_paths:
                self.icon_cap = cv2.VideoCapture(self.icon_paths["DB"])
            elif "WV" in self.icon_paths:
                self.icon_cap = cv2.VideoCapture(self.icon_paths["WV"])
        else:
            # 其他等级正常匹配
            if key in self.icon_paths: 
                self.icon_cap = cv2.VideoCapture(self.icon_paths[key])
            elif key in ["C6", "C5"] and "C5" in self.icon_paths: 
                self.icon_cap = cv2.VideoCapture(self.icon_paths["C5"])
            
        self.active_icon_key = cache_key
        return self.icon_cap

    def get_timeline_cap(self, month):
        if self.active_timeline_month != month:
            if self.timeline_cap: 
                self.timeline_cap.release()
                self.timeline_cap = None
            if month in self.month_paths:
                self.timeline_cap = cv2.VideoCapture(self.month_paths[month])
            self.active_timeline_month = month
        return self.timeline_cap
        
    def release_all(self):
        if self.icon_cap: self.icon_cap.release()
        if self.timeline_cap: self.timeline_cap.release()

# ================= 核心 5：总结条状态机 =================
class SummaryCard:
    def __init__(self, storm_data, slot_index, trigger_frame, width, media_lib):
        self.storm = storm_data
        self.start_frame = trigger_frame
        cat = get_icon_key("TC", storm_data['peak'])
        
        self.cap = None
        if cat in media_lib.summary_paths:
            self.cap = cv2.VideoCapture(media_lib.summary_paths[cat])
        elif "C5" in media_lib.summary_paths:
            self.cap = cv2.VideoCapture(media_lib.summary_paths["C5"])

        self.card_w, self.card_h = 580, 180 
        self.target_x = width - self.card_w - 30
        self.hidden_x = width
        self.y = 50 + slot_index * (self.card_h + 20)
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
            if progress >= 1.0: self.state = "staying"
        elif self.state == "staying":
            self.timer += 1
            if self.timer > 120: self.state = "sliding_out"
        elif self.state == "sliding_out":
            self.timer += 1
            progress = min(1.0, self.timer / 30.0)
            ease = 1 - pow(1 - progress, 3)
            self.current_x = int(self.target_x + (self.hidden_x - self.target_x) * ease)
            if progress >= 1.0: self.state = "gone"
        return self.state != "gone"

    def draw(self, frame, h, w):
        if self.state == "gone" or not self.cap: return
        ret, sum_frame = self.cap.read()
        if not ret:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, sum_frame = self.cap.read()
            
        if ret:
            sum_frame = cv2.resize(sum_frame, (self.card_w, self.card_h))
            x, y = self.current_x, self.y
            top, left = max(0, y), max(0, x)
            bot, right = min(h, y+self.card_h), min(w, x+self.card_w)
            
            if top < bot and left < right:
                ic_y1, ic_y2 = top-y, bot-y
                ic_x1, ic_x2 = left-x, right-x
                ic = sum_frame[ic_y1:ic_y2, ic_x1:ic_x2]
                roi = frame[top:bot, left:right]
                
                bg_f = roi.astype(np.float32) / 255.0
                fg_f = ic.astype(np.float32) / 255.0
                res = 1.0 - (1.0 - bg_f) * (1.0 - fg_f)
                frame[top:bot, left:right] = (np.clip(res, 0, 1) * 255.0).astype(np.uint8)
                
                cv2.putText(frame, f"{self.storm.get('name', '')}", (left+30, top+70), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)
                cv2.putText(frame, f"Peak: {self.storm['peak']}kt", (left+30, top+120), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)

    def release(self):
        if self.cap: self.cap.release()

# ================= 核心 6：终极渲染主循环 =================
def render_logic(folder_path, bdeck_path, target_peak, update_ui):
    try:
        update_ui("扫描满配素材库...", "orange")
        media = MediaLibrary(folder_path)
        if media.map_bg is None:
            update_ui("❌ 未找到底图 WPAC.png", "red")
            return

        update_ui(f"解析 B-deck，高斯拉伸至 {target_peak}kt", "orange")
        records = parse_and_smooth_bdeck(bdeck_path, target_peak)
        if not records: return

        start_date, end_date = records[0]['time'], records[-1]['time']
        active_intervals = [(r['time'], r['time'] + timedelta(hours=6)) for r in records]
        
        mapper = TimeMapper(start_date, end_date, active_intervals)
        total_frames = len(mapper.frame_times)
        
        bg = cv2.resize(media.map_bg, (1080, 1920))
        h, w = bg.shape[:2]

        out_path = "/storage/emulated/0/Download/Typhoon_Output.mp4"
        if not os.path.exists("/storage/emulated/0/Download"): out_path = "out.mp4"
        
        writer = subprocess.Popen(
            ['ffmpeg', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{w}x{h}', '-r', '30', '-i', '-', '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-pix_fmt', 'yuv420p', out_path],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )

        cards = []
        storm_info = {"name": records[0].get('name', 'Real Storm'), "peak": target_peak}
        cards.append(SummaryCard(storm_info, 0, max(0, total_frames - 120), w, media))

        ace_accum, ace_list = 0.0, []
        for r in records:
            ace_accum += (r['fused_vmax'] ** 2) / 10000.0
            ace_list.append(ace_accum)

        for frame_idx in range(total_frames):
            curr_time = mapper.get_time(frame_idx)
            frame = bg.copy()
            
            closest_idx = min(range(len(records)), key=lambda i: abs((records[i]['time'] - curr_time).total_seconds()))
            r = records[closest_idx]
            px, py = int((r['lon'] - 100) / 80 * w), int((50 - r['lat']) / 50 * h)
            current_ace = ace_list[closest_idx]

            # 获取图标
            icon_key = get_icon_key(r['nature'], r['fused_vmax'])
            icon_cap = media.get_icon_cap(icon_key, r['nature'])

            if icon_cap and icon_cap.isOpened():
                ret, icon_frame = icon_cap.read()
                if not ret:
                    icon_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, icon_frame = icon_cap.read()
                if ret:
                    icon_frame = cv2.resize(icon_frame, (150, 150))
                    top, left = max(0, py-75), max(0, px-75)
                    bot, right = min(h, top+150), min(w, left+150)
                    if top < bot and left < right:
                        ic = icon_frame[0:bot-top, 0:right-left]
                        roi = frame[top:bot, left:right]
                        bg_f = roi.astype(np.float32) / 255.0
                        fg_f = ic.astype(np.float32) / 255.0
                        res = 1.0 - (1.0 - bg_f) * (1.0 - fg_f)
                        frame[top:bot, left:right] = (np.clip(res, 0, 1) * 255.0).astype(np.uint8)

            # 月份时间轴
            timeline_cap = media.get_timeline_cap(curr_time.month)
            if timeline_cap:
                sec = curr_time.hour * 3600 + curr_time.minute * 60
                total_f = timeline_cap.get(cv2.CAP_PROP_FRAME_COUNT)
                frame_idx_tl = int((sec / 86400) * total_f) 
                timeline_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx_tl)
                ret_r, ring_frame = timeline_cap.read()
                if ret_r:
                    ring_frame = cv2.resize(ring_frame, (300, 300))
                    roi = frame[h-320:h-20, 20:320]
                    if roi.shape == ring_frame.shape:
                        bg_f = roi.astype(np.float32) / 255.0
                        fg_f = ring_frame.astype(np.float32) / 255.0
                        res = 1.0 - (1.0 - bg_f) * (1.0 - fg_f)
                        frame[h-320:h-20, 20:320] = (np.clip(res, 0, 1) * 255.0).astype(np.uint8)
            
            cv2.putText(frame, curr_time.strftime('%Y-%m-%d %H:%M'), (30, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            if media.ace_bg is not None:
                bg_img = cv2.resize(media.ace_bg, (350, 200))
                frame[h-220:h-20, w-370:w-20] = bg_img
                
                bar_y = h - 120
                bar_max_w = 310
                current_w = min(bar_max_w, max(0, int((current_ace / 600.0) * bar_max_w)))
                cv2.rectangle(frame, (w-350, bar_y), (w-350+current_w, bar_y+15), (0, 255, 255), -1)

            for card in cards:
                if card.update(frame_idx):
                    card.draw(frame, h, w)

            writer.stdin.write(frame.tobytes())
            if frame_idx % 100 == 0: update_ui(f"渲染进度: {frame_idx}/{total_frames}", "orange")

        media.release_all()
        for c in cards: c.release()
        writer.stdin.close(); writer.wait()
        update_ui(f"✅ 渲染完成！已保存至 {out_path}", "green")

    except Exception as e:
        update_ui(f"❌ 渲染失败: {e}", "red")

# ================= Flet 界面 =================
def main(page: ft.Page):
    page.title = "台风视觉引擎 (高斯+性质融合版)"
    page.theme_mode = ft.ThemeMode.DARK
    
    log_box = ft.TextField(multiline=True, read_only=True, height=150)
    status_text = ft.Text("请导入 B-deck 文件", color="green")
    peak_input = ft.TextField(label="自评巅峰风速 (kt)", value="170", width=200)

    paths = {"bdeck": ""}

    def update_ui(msg, color):
        log_box.value += msg + "\n"
        status_text.value = msg
        status_text.color = color
        page.update()

    def handle_bdeck(e: ft.FilePickerResultEvent):
        if e.files:
            paths["bdeck"] = e.files[0].path
            update_ui(f"B-deck: {e.files[0].name}", "white")

    bdeck_picker = ft.FilePicker(on_result=handle_bdeck)
    page.services.append(bdeck_picker)

    def start_sim(e):
        if not paths["bdeck"]:
            update_ui("❌ 请选择 B-deck 报文！", "red")
            return
        try:
            target_peak = int(peak_input.value)
        except:
            target_peak = 170
        
        folder_path = "assets" 
        
        threading.Thread(target=render_logic, args=(folder_path, paths["bdeck"], target_peak, update_ui), daemon=True).start()

    page.add(
        ft.Container(
            content=ft.Column([
                ft.Text("全自动动态特效渲染", size=20, weight=ft.FontWeight.BOLD),
                ft.Text("WV、LO、DB 同等视为未成型系统，依据风速自动匹配图标", size=12, color="grey"),
                ft.Divider(),
                ft.Row([ft.Button("1. 导入 B-deck 文件", action=ft.PickFiles(bdeck_picker, allowed_extensions=["txt", "dat"])), peak_input]),
                ft.Button("▶ 启动渲染", on_click=start_sim, bgcolor="orange", color="white", width=300),
                status_text,
                log_box
            ]),
            padding=20
        )
    )

if __name__ == "__main__":
    ft.run(main)
