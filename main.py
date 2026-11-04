import flet as ft
import cv2
import numpy as np
import threading
import os
import math
import zipfile
from datetime import datetime, timedelta

# ================= 核心 0：距离计算公式 =================
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# ================= 核心 1：纯正 JTWC 德法 5KT 整数表 =================
def cma_ms_to_kt_dvorak(vmax_ms):
    v = round(vmax_ms)
    if v >= 78: return 185
    elif v >= 75: return 170
    elif v >= 68: return 155
    elif v >= 62: return 140
    elif v >= 58: return 125
    elif v >= 52: return 115
    elif v >= 48: return 100
    elif v >= 42: return 90
    elif v >= 38: return 75
    elif v >= 33: return 65
    elif v >= 28: return 55
    elif v >= 23: return 45
    elif v >= 18: return 35
    elif v >= 15: return 30
    else: return 25

def get_icon_key(nature, vmax):
    nature = nature.upper()
    if nature in ["EX", "SS", "SD"]: return nature
    if nature == "MD": return "MD"
    if vmax < 25: return "DB"
    elif vmax < 34: return "TD"
    elif vmax < 64: return "TS"
    elif vmax < 83: return "C1"
    elif vmax < 96: return "C2"
    elif vmax < 113: return "C3"
    elif vmax < 137: return "C4"
    elif vmax < 170: return "C5"
    else: return "C6"

# ================= 核心 2：UI 名单提取 =================
def extract_storms_info(filepath):
    storms = []
    current_storm = None
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if line.startswith("66666"):
                    parts = line.split()
                    if len(parts) > 7:
                        name = parts[7]
                        if name == "(nameless)" or name == "nameless": 
                            name = f"无名_{parts[3]}"
                        current_storm = {"name": name, "raw_peak_wind": 0.0, "raw_peak_press": 1010}
                        storms.append(current_storm)
                elif current_storm and line:
                    parts = line.split()
                    if len(parts) >= 6:
                        try:
                            vmax_ms = float(parts[5])
                            pressure = int(parts[4])
                            if vmax_ms > current_storm["raw_peak_wind"]:
                                current_storm["raw_peak_wind"] = vmax_ms
                                current_storm["raw_peak_press"] = pressure
                        except: pass
    except: pass
    return storms

# ================= 核心 3：解析与风压双控 =================
def parse_multi_storms(filepath, user_peaks_wind, user_peaks_press):
    all_storms = []
    current_storm = None
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                if line.startswith("66666"):
                    if current_storm and current_storm["records"]:
                        all_storms.append(current_storm)
                    parts = line.split()
                    if len(parts) > 7:
                        name = parts[7]
                        if name == "(nameless)" or name == "nameless": 
                            name = f"无名_{parts[3]}"
                        current_storm = {"name": name, "records": []}
                    continue
                    
                if current_storm is None: continue
                parts = line.split()
                if len(parts) < 6: continue
                try:
                    t = datetime.strptime(parts[0], '%Y%m%d%H')
                    lvl = parts[1]
                    nature = "TC" if lvl in ['4','5','6'] else ("EX" if lvl == '9' else ("TS" if lvl == '3' else "TD"))
                    lat = float(parts[2])/10.0
                    lon = float(parts[3])/10.0
                    vmax_ms = float(parts[5])
                    pressure = int(parts[4])
                    
                    jtc_vmax = cma_ms_to_kt_dvorak(vmax_ms)
                    current_storm["records"].append({
                        'time': t, 'lat': lat, 'lon': lon, 
                        'jtc_vmax': jtc_vmax, 'pressure': pressure, 'nature': nature
                    })
                except: pass
        if current_storm and current_storm["records"]:
            all_storms.append(current_storm)
    except Exception as e:
        print(f"Read error: {e}")

    for storm in all_storms:
        records = storm["records"]
        if not records: continue
        max_jtc_wind = max(r['jtc_vmax'] for r in records)
        peak_idx = next(i for i, r in enumerate(records) if r['jtc_vmax'] == max_jtc_wind)
        peak_press = records[peak_idx]['pressure']
        
        target_wind = int(round(user_peaks_wind.get(storm["name"], max_jtc_wind) / 5.0) * 5)
        target_press = int(round(user_peaks_press.get(storm["name"], peak_press)))
        
        delta_v = target_wind - max_jtc_wind if target_wind > max_jtc_wind else 0
        delta_p = peak_press - target_press if target_press < peak_press else 0
        
        sigma = max(2, len(records) / 12.0)
        
        for i in range(len(records)):
            dist = i - peak_idx
            weight = math.exp(-(dist ** 2) / (2 * (sigma ** 2)))
            if weight > 0.05:
                raw_wind = records[i]['jtc_vmax'] + delta_v * weight
                records[i]['fused_wind'] = int(round(raw_wind / 5.0) * 5)
                records[i]['fused_press'] = int(round(records[i]['pressure'] - delta_p * weight))
            else:
                records[i]['fused_wind'] = records[i]['jtc_vmax']
                records[i]['fused_press'] = records[i]['pressure']
                
        for r in records:
            if r['fused_wind'] > target_wind: r['fused_wind'] = target_wind
            if r['fused_press'] < target_press: r['fused_press'] = target_press
            if delta_p == 0: r['fused_press'] = r['pressure']
            if delta_v == 0: r['fused_wind'] = r['jtc_vmax']

        storm["start_time"] = records[0]['time']
        storm["end_time"] = records[-1]['time']
        storm['peak_wind'] = max(r['fused_wind'] for r in records)
        storm['peak_press'] = min(r['fused_press'] for r in records)
        
        storm['life_hours'] = int((storm["end_time"] - storm["start_time"]).total_seconds() / 3600.0)
        total_dist = 0.0
        for i in range(1, len(records)):
            total_dist += haversine(records[i-1]['lat'], records[i-1]['lon'], records[i]['lat'], records[i]['lon'])
        storm['track_km'] = int(total_dist)
    return sorted(all_storms, key=lambda x: x["start_time"])

# ================= 核心 4：时间映射 =================
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

# ================= 核心 5：素材库 =================
class MediaLibrary:
    def __init__(self, folder_path):
        self.icon_paths, self.summary_paths, self.month_paths = {}, {}, {}
        self.ace_bg, self.map_bg = None, None
        self.active_icon_key, self.icon_cap = None, None
        self.active_timeline_month, self.timeline_cap = -1, None

        if not os.path.exists(folder_path): return
        def read_image_safe(p):
            try:
                img = cv2.imread(p)
                if img is not None: return img
                img_array = np.fromfile(p, dtype=np.uint8)
                return cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            except: return None

        for f in os.listdir(folder_path):
            f_lower = f.lower()
            path = os.path.join(folder_path, f)
            f_upper = f.upper()

            if "wpac" in f_lower and f_lower.endswith(".png"): self.map_bg = read_image_safe(path)
            elif "ace_gui" in f_lower and f_lower.endswith(".png"): self.ace_bg = read_image_safe(path)
            elif f_lower.endswith(".mp4"):
                months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
                for i, m in enumerate(months):
                    if m in f_upper and "summary" not in f_lower:
                        self.month_paths[i+1] = path
                        break
                if "SUMMARY" not in f_upper:
                    if "N-DB-AWV" in f_upper: self.icon_paths["WV"] = path 
                    elif "N-DB-AL" in f_upper: self.icon_paths["LO"] = path 
                    elif "N-DB-" in f_upper: self.icon_paths["DB"] = path 
                    elif "N-TD-" in f_upper or "N-TC-" in f_upper or "N-EX-" in f_upper:
                        cat = f_upper.replace(".MP4", "").split("-")[-1]
                        self.icon_paths[cat] = path
                elif "SUMMARY-N-TC-" in f_upper:
                    cat = f_upper.replace(".MP4", "").split("SUMMARY-N-TC-")[-1]
                    self.summary_paths[cat] = path

    def get_icon_cap(self, key, nature=""):
        nature = nature.upper()
        cache_key = f"{key}_{nature}"
        if self.active_icon_key == cache_key and self.icon_cap: return self.icon_cap
        if self.icon_cap: self.icon_cap.release(); self.icon_cap = None
        if key == "DB":
            if nature == "WV" and "WV" in self.icon_paths: self.icon_cap = cv2.VideoCapture(self.icon_paths["WV"])
            elif nature == "LO" and "LO" in self.icon_paths: self.icon_cap = cv2.VideoCapture(self.icon_paths["LO"])
            elif "DB" in self.icon_paths: self.icon_cap = cv2.VideoCapture(self.icon_paths["DB"])
        else:
            if key in self.icon_paths: self.icon_cap = cv2.VideoCapture(self.icon_paths[key])
            elif key in ["C6", "C5"] and "C5" in self.icon_paths: self.icon_cap = cv2.VideoCapture(self.icon_paths["C5"])
        self.active_icon_key = cache_key
        return self.icon_cap

    def get_timeline_cap(self, month):
        if self.active_timeline_month != month:
            if self.timeline_cap: self.timeline_cap.release(); self.timeline_cap = None
            if month in self.month_paths: self.timeline_cap = cv2.VideoCapture(self.month_paths[month])
            self.active_timeline_month = month
        return self.timeline_cap

    def release_all(self):
        if self.icon_cap: self.icon_cap.release()
        if self.timeline_cap: self.timeline_cap.release()

# ================= 核心 6：总结条 =================
class SummaryCard:
    def __init__(self, storm_data, slot_index, trigger_frame, width, media_lib):
        self.storm = storm_data
        self.start_frame = trigger_frame
        cat = get_icon_key("TC", storm_data['peak_wind'])
        self.cap = None
        if cat in media_lib.summary_paths: self.cap = cv2.VideoCapture(media_lib.summary_paths[cat])
        elif "C5" in media_lib.summary_paths: self.cap = cv2.VideoCapture(media_lib.summary_paths["C5"])

        self.card_w, self.card_h = 580, 180 
        self.target_x, self.hidden_x = width - self.card_w - 30, width
        self.y = 50 + slot_index * (self.card_h + 20)
        self.state, self.timer, self.current_x = "sliding_in", 0, self.hidden_x

    def update(self, frame_idx):
        t = frame_idx - self.start_frame
        if t < 0: return False
        if self.state == "sliding_in":
            self.timer += 1
            progress = min(1.0, self.timer / 30.0)
            self.current_x = int(self.hidden_x - (self.hidden_x - self.target_x) * (1 - pow(1 - progress, 3)))
            if progress >= 1.0: self.state = "staying"
        elif self.state == "staying":
            self.timer += 1
            if self.timer > 120: self.state = "sliding_out"
        elif self.state == "sliding_out":
            self.timer += 1
            progress = min(1.0, self.timer / 30.0)
            self.current_x = int(self.target_x + (self.hidden_x - self.target_x) * (1 - pow(1 - progress, 3)))
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
                ic = sum_frame[top-y:bot-y, left-x:right-x]
                roi = frame[top:bot, left:right]
                bg_f = roi.astype(np.float32) / 255.0
                fg_f = ic.astype(np.float32) / 255.0
                res = 1.0 - (1.0 - bg_f) * (1.0 - fg_f)
                frame[top:bot, left:right] = (np.clip(res, 0, 1) * 255.0).astype(np.uint8)
                
                cv2.putText(frame, f"{self.storm.get('name', '')}", (left+30, top+50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
                cv2.putText(frame, f"Peak: {self.storm['peak_wind']}kt / {self.storm['peak_press']}hPa", (left+30, top+95), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                cv2.putText(frame, f"Life: {self.storm['life_hours']}h | Track: {self.storm['track_km']}km", (left+30, top+140), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
    def release(self):
        if self.cap: self.cap.release()

# ================= 核心 7：渲染主循环 =================
def render_logic(folder_path, bdeck_path, user_wind, user_press, update_ui, trigger_save_dialog):
    try:
        update_ui(f"扫描目录: {folder_path}", "orange")
        media = MediaLibrary(folder_path)
        if media.map_bg is None:
            update_ui(f"❌ 未找到底图 WPAC.png", "red")
            return

        update_ui("解析整年风季数据...", "orange")
        all_storms = parse_multi_storms(bdeck_path, user_wind, user_press)
        if not all_storms: 
            update_ui("❌ 数据解析为空", "red")
            return

        active_intervals = [(s["start_time"], s["end_time"]) for s in all_storms]
        overall_start = min(s["start_time"] for s in all_storms)
        overall_end = max(s["end_time"] for s in all_storms)
        
        mapper = TimeMapper(overall_start, overall_end, active_intervals)
        total_frames = len(mapper.frame_times)
        update_ui(f"时间轴总帧数: {total_frames}，开始渲染...", "green")
        
        bg = cv2.resize(media.map_bg, (1080, 1920))
        h, w = bg.shape[:2]

        # 直接写在你之前成功生成的那个 app 目录
        app_dir = os.path.dirname(os.path.abspath(__file__))
        safe_path = os.path.join(app_dir, "Typhoon_Season_Output.mp4")
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(safe_path, fourcc, 30.0, (w, h))
        
        if not writer.isOpened():
            update_ui(f"❌ 视频创建失败，可能是编码器不支持！", "red")
            return

        cards = []
        slot_counter = 0
        last_trigger_frame = -9999
        
        storms_sorted_by_end = sorted(all_storms, key=lambda x: x["end_time"])
        
        for storm in storms_sorted_by_end:
            if storm['peak_wind'] < 25: continue 
            life_hours = (storm["end_time"] - storm["start_time"]).total_seconds() / 3600.0
            if life_hours < 24: continue 
                
            end_frame = next((idx for idx, t in enumerate(mapper.frame_times) if t >= storm["end_time"]), total_frames - 1)
            start_frame = next((idx for idx, t in enumerate(mapper.frame_times) if t >= storm["start_time"]), 0)
            
            trigger = max(start_frame, end_frame - 120)
            if trigger < last_trigger_frame + 60:
                trigger = last_trigger_frame + 60
            if trigger >= total_frames:
                trigger = max(0, total_frames - 180)
                
            last_trigger_frame = trigger
            cards.append(SummaryCard(storm, slot_counter % 3, trigger, w, media))
            slot_counter += 1

        ace_accum = 0.0

        for frame_idx in range(total_frames):
            curr_time = mapper.get_time(frame_idx)
            frame = bg.copy()
            ace_increment = 0.0
            
            for storm in all_storms:
                if storm["start_time"] <= curr_time <= storm["end_time"]:
                    closest_idx = min(range(len(storm["records"])), key=lambda i: abs((storm["records"][i]['time'] - curr_time).total_seconds()))
                    r = storm["records"][closest_idx]
                    
                    px, py = int((r['lon'] - 100) / 80 * w), int((50 - r['lat']) / 50 * h)
                    ace_increment += (r['fused_wind'] ** 2) / 10000.0

                    icon_key = get_icon_key(r['nature'], r['fused_wind'])
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

            ace_accum += ace_increment
            
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
                current_w = min(bar_max_w, max(0, int((ace_accum / 600.0) * bar_max_w)))
                cv2.rectangle(frame, (w-350, bar_y), (w-350+current_w, bar_y+15), (0, 255, 255), -1)

            for card in cards:
                if card.update(frame_idx):
                    card.draw(frame, h, w)

            writer.write(frame)
            
            if frame_idx % 100 == 0: 
                update_ui(f"渲染进度: {frame_idx}/{total_frames}", "orange")

        media.release_all()
        for c in cards: c.release()
        writer.release()
        
        if os.path.exists(safe_path):
            update_ui("✅ 渲染完成！正在唤起系统保存窗口...", "green")
            trigger_save_dialog(safe_path)
        else:
            update_ui("❌ 渲染完成但文件未找到！", "red")

    except Exception as e:
        update_ui(f"❌ 渲染失败: {e}", "red")

# ================= Flet 界面 =================
def main(page: ft.Page):
    page.title = "整年风季动画渲染"
    page.theme_mode = ft.ThemeMode.DARK
    page.scroll = ft.ScrollMode.AUTO
    
    log_box = ft.TextField(multiline=True, read_only=True, height=100)
    status_text = ft.Text("请先导入素材 ZIP 包", color="green")
    
    paths = {"bdeck": "", "assets": ""}
    wind_inputs = {}
    press_inputs = {}

    file_saver = ft.FilePicker()
    page.services.append(file_saver)

    def update_ui(msg, color):
        log_box.value += msg + "\n"
        status_text.value = msg
        status_text.color = color
        page.update()

    def trigger_save_dialog(safe_path):
        try:
            with open(safe_path, "rb") as f:
                data = f.read()
                
            file_saver.save_file(
                dialog_title="请选择保存位置 (例如 Download 文件夹)",
                file_name="Typhoon_Season_Full.mp4",
                src_bytes=data
            )
            update_ui(f"✅ 请在弹出的系统窗口中选择 Download 保存！", "green")
        except Exception as e:
            update_ui(f"❌ 唤起保存窗口失败: {e}", "red")

    storms_ui_container = ft.Column(spacing=10)

    def handle_zip(e: ft.FilePickerResultEvent):
        if e.files:
            zip_path = e.files[0].path
            update_ui("正在解压并智能寻路...", "orange")
            # 改回存进 __file__ 目录
            local_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_assets")
            
            def extract_task():
                try:
                    if not os.path.exists(local_dir): os.makedirs(local_dir)
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(local_dir)
                    
                    real_assets_dir = local_dir
                    for root, dirs, files in os.walk(local_dir):
                        if any(f.lower() == 'wpac.png' for f in files):
                            real_assets_dir = root
                            break
                    
                    paths["assets"] = real_assets_dir
                    file_count = len(os.listdir(real_assets_dir))
                    
                    if file_count == 0:
                        update_ui(f"❌ 解压成功，但文件夹是空的！", "red")
                    else:
                        update_ui(f"✅ 解压成功！找到 {file_count} 个文件，目录已锁定。", "green")
                except Exception as ex:
                    update_ui(f"❌ 解压失败: {ex}", "red")
            
            threading.Thread(target=extract_task, daemon=True).start()

    zip_picker = ft.FilePicker(on_result=handle_zip)
    page.services.append(zip_picker)

    def handle_bdeck(e: ft.FilePickerResultEvent):
        if e.files:
            paths["bdeck"] = e.files[0].path
            update_ui(f"数据已导入: {e.files[0].name}", "white")
            
            storms = extract_storms_info(paths["bdeck"])
            storms_ui_container.controls.clear()
            wind_inputs.clear()
            press_inputs.clear()
            
            storms_ui_container.controls.append(
                ft.Row([
                    ft.Text("台风名", width=100, weight=ft.FontWeight.BOLD, color="orange"),
                    ft.Text("巅峰风速(kt)", width=100, weight=ft.FontWeight.BOLD, color="orange"),
                    ft.Text("最低气压(hPa)", width=100, weight=ft.FontWeight.BOLD, color="orange")
                ])
            )
            
            for s in storms:
                name = s["name"]
                dvorak_kt = cma_ms_to_kt_dvorak(s["raw_peak_wind"])
                raw_press = s["raw_peak_press"]
                
                w_inp = ft.TextField(value=str(dvorak_kt), width=80, height=40, text_size=14, content_padding=10)
                p_inp = ft.TextField(value=str(raw_press), width=80, height=40, text_size=14, content_padding=10)
                wind_inputs[name] = w_inp
                press_inputs[name] = p_inp
                
                row = ft.Row([
                    ft.Text(f"{name}", width=100, size=14),
                    w_inp,
                    p_inp,
                    ft.Text(f"(原: {dvorak_kt}kt / {raw_press}hPa)", color="grey", size=12)
                ], alignment=ft.MainAxisAlignment.START)
                storms_ui_container.controls.append(row)
            page.update()

    bdeck_picker = ft.FilePicker(on_result=handle_bdeck)
    page.services.append(bdeck_picker)

    def start_sim(e):
        if not paths["bdeck"]: 
            update_ui("❌ 请先导入数据文件！", "red")
            return
        if not paths["assets"]: 
            update_ui("❌ 请先导入素材 ZIP 包！", "red")
            return
        
        user_wind = {}
        user_press = {}
        for name, w_inp in wind_inputs.items():
            try: user_wind[name] = int(w_inp.value)
            except: pass
        for name, p_inp in press_inputs.items():
            try: user_press[name] = int(p_inp.value)
            except: pass
                
        update_ui("开始渲染整年风季...", "orange")
        threading.Thread(target=render_logic, args=(paths["assets"], paths["bdeck"], user_wind, user_press, update_ui, trigger_save_dialog), daemon=True).start()

    page.add(
        ft.Container(
            content=ft.Column([
                ft.Text("整年风季动画渲染", size=20, weight=ft.FontWeight.BOLD),
                ft.Text("渲染结束后，系统会自动弹出保存窗口", size=12, color="grey"),
                ft.Divider(),
                ft.Row([
                    ft.Button("1. 导入素材 ZIP 包", action=ft.PickFiles(zip_picker, allowed_extensions=["zip"]), bgcolor="teal", color="white"),
                ]),
                ft.Row([
                    ft.Button("2. 导入整年 CMA 数据", action=ft.PickFiles(bdeck_picker, allowed_extensions=["txt", "dat"]), bgcolor="blue", color="white"),
                ]),
                storms_ui_container,
                ft.Divider(),
                ft.Button("▶ 确认自评并启动整年渲染", on_click=start_sim, bgcolor="orange", color="white", width=300),
                status_text,
                log_box
            ]),
            padding=20
        )
    )

if __name__ == "__main__":
    ft.run(main)
