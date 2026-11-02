import flet as ft
import cv2
import numpy as np
import threading
import os
import math
from datetime import datetime, timedelta
from PIL import Image, ImageDraw

# ================= 核心引擎 1：B-deck 数据解析 =================
def parse_bdeck(filepath):
    records = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if line.startswith('#') or not line.strip(): continue
                parts = line.split(',')
                if len(parts) < 11: continue
                try:
                    t = datetime.strptime(parts[2].strip(), '%Y%m%d%H')
                    lat = float(parts[6].strip()[:-1]) / 10.0
                    if parts[6].strip()[-1] == 'S': lat = -lat
                    lon = float(parts[7].strip()[:-1]) / 10.0
                    if parts[7].strip()[-1] == 'W': lon = 360 - lon
                    vmax = int(parts[8].strip())
                    status = parts[10].strip()
                    records.append({'time': t, 'lat': lat, 'lon': lon, 'vmax': vmax, 'status': status})
                except: continue
    except Exception as e:
        print(f"读取B-deck出错: {e}")
    return sorted(records, key=lambda x: x['time'])

# 曲线插值 (Catmull-Rom)
def catmull_rom(p0, p1, p2, p3, t):
    t2 = t * t; t3 = t2 * t
    return 0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)

def get_smooth_pos(records, current_time):
    if current_time <= records[0]['time']: return records[0]
    if current_time >= records[-1]['time']: return records[-1]
    for i in range(len(records) - 1):
        if records[i]['time'] <= current_time <= records[i+1]['time']:
            t = (current_time - records[i]['time']).total_seconds() / (records[i+1]['time'] - records[i]['time']).total_seconds()
            p0 = records[max(0, i-1)]; p1 = records[i]; p2 = records[i+1]; p3 = records[min(len(records)-1, i+2)]
            lat = catmull_rom(p0['lat'], p1['lat'], p2['lat'], p3['lat'], t)
            lon = catmull_rom(p0['lon'], p1['lon'], p2['lon'], p3['lon'], t)
            vmax = p1['vmax'] + (p2['vmax'] - p1['vmax']) * t
            return {'time': current_time, 'lat': lat, 'lon': lon, 'vmax': vmax, 'status': p1['status']}
    return records[-1]

# ================= 核心引擎 2：渲染与特效 =================
def get_color(vmax):
    if vmax < 34: return (255, 200, 0)
    if vmax < 64: return (0, 255, 0)
    if vmax < 83: return (0, 255, 255)
    if vmax < 113: return (0, 0, 255)
    return (255, 0, 255)

def render_logic(bdeck_file, bg_path, icon_path, update_ui):
    try:
        update_ui("正在解析 B-deck 数据...", "orange")
        records = parse_bdeck(bdeck_file)
        if len(records) < 2:
            update_ui("❌ B-deck 数据不足，请确认你选的真的是bdeck文件", "red")
            return

        update_ui(f"解析成功，共 {len(records)} 条记录。开始渲染...", "orange")

        bg = cv2.imread(bg_path)
        if bg is None:
            update_ui("❌ 找不到底图，可能是图片格式不支持", "red")
            return
        bg = cv2.resize(bg, (1080, 1920))
        h, w = bg.shape[:2]

        # 输出路径咱们就放手机相册根目录下的Download，保证有权限！
        out_path = "/storage/emulated/0/Download/final_typhoon_output.mp4"

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(out_path, fourcc, 30.0, (w, h))
        
        cap_icon = cv2.VideoCapture(icon_path)
        has_icon = cap_icon.isOpened()

        total_frames = 150 # 缩短帧数，先测试跑通
        ace_total = 0.0

        for frame_idx in range(total_frames):
            start_t = records[0]['time']
            end_t = records[-1]['time']
            current_t = start_t + (end_t - start_t) * (frame_idx / total_frames)
            
            pos = get_smooth_pos(records, current_t)
            
            if frame_idx % 10 == 0:
                ace_total += (pos['vmax'] ** 2) / 100000.0

            px = int((pos['lon'] - 100) / 80 * w)
            py = int((50 - pos['lat']) / 50 * h)
            px = max(50, min(w-50, px))
            py = max(50, min(h-50, py))

            frame = bg.copy()

            for i in range(len(records) - 1):
                if records[i]['time'] > current_t: break
                pt1 = (int((records[i]['lon'] - 100) / 80 * w), int((50 - records[i]['lat']) / 50 * h))
                pt2 = (int((records[i+1]['lon'] - 100) / 80 * w), int((50 - records[i+1]['lat']) / 50 * h))
                cv2.line(frame, pt1, pt2, get_color(records[i]['vmax']), 5)

            if has_icon:
                ret, icon_frame = cap_icon.read()
                if not ret:
                    cap_icon.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, icon_frame = cap_icon.read()
                if ret:
                    icon_frame = cv2.resize(icon_frame, (120, 120))
                    top, left = max(0, py-60), max(0, px-60)
                    bot, right = min(h, top+120), min(w, left+120)
                    roi = frame[top:bot, left:right]
                    ic = icon_frame[0:bot-top, 0:right-left]
                    frame[top:bot, left:right] = cv2.addWeighted(roi, 0.5, ic, 0.5, 0)

            pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            draw = ImageDraw.Draw(pil_img)
            
            draw.rectangle([(30, 30), (450, 80)], fill=(0, 0, 0))
            draw.text((40, 40), f"UTC: {current_t.strftime('%Y-%m-%d %H:%M')}", fill=(255, 255, 255))
            
            draw.rectangle([(w-250, 30), (w-30, 80)], fill=(0, 0, 0))
            draw.text((w-230, 40), f"ACE: {ace_total:.2f}", fill=(255, 255, 0))

            frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            out.write(frame)

        if has_icon: cap_icon.release()
        out.release()
        update_ui(f"✅ 渲染完成！已输出到手机下载目录: Download/final_typhoon_output.mp4", "green")

    except Exception as e:
        update_ui(f"❌ 渲染失败: {e}", "red")

# ================= Flet 界面 =================
def main(page: ft.Page):
    page.title = "台风生成器 (完全体)"
    page.theme_mode = ft.ThemeMode.DARK

    status_text = ft.Text("请先选择你的文件！", size=14, color="green")
    log_box = ft.TextField(multiline=True, read_only=True, height=100)

    # 存储选中的文件路径
    paths = {"bdeck": "", "bg": "", "icon": ""}
    file_picker = ft.FilePicker()
    page.overlay.append(file_picker)

    def update_ui(msg, color):
        log_box.value += msg + "\n"
        status_text.value = msg
        status_text.color = color
        page.update()

    # 文件选择回调
    async def pick_bdeck(e):
        res = await file_picker.pick_files(allow_multiple=False)
        if res: 
            paths["bdeck"] = res[0].path
            update_ui(f"已选B-deck: {res[0].name}", "white")

    async def pick_bg(e):
        res = await file_picker.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.IMAGE)
        if res: 
            paths["bg"] = res[0].path
            update_ui(f"已选底图: {res[0].name}", "white")

    async def pick_icon(e):
        res = await file_picker.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.VIDEO)
        if res: 
            paths["icon"] = res[0].path
            update_ui(f"已选图标: {res[0].name}", "white")

    def start_render(e):
        if not paths["bdeck"] or not paths["bg"]:
            update_ui("❌ 必须选B-deck和底图才能开工！", "red")
            return
        
        log_box.value = "开始渲染任务...\n"
        page.update()
        # 图标没选就传空字符串
        threading.Thread(target=render_logic, args=(paths["bdeck"], paths["bg"], paths["icon"], update_ui)).start()

    page.add(
        ft.Container(
            content=ft.Column([
                ft.Text("西北太平洋台风季生成器 (完全体)", size=22, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                ft.Container(
                    padding=10,
                    bgcolor="#222222",
                    border_radius=5,
                    content=ft.Column([
                        ft.Text("数据源选择", weight=ft.FontWeight.BOLD),
                        ft.Row([ft.Button("1. 选择 B-deck 文件", on_click=pick_bdeck)]),
                        ft.Row([ft.Button("2. 选择底图 PNG", on_click=pick_bg)]),
                        ft.Row([ft.Button("3. 选择图标 MP4", on_click=pick_icon)]),
                    ])
                ),
                ft.Divider(),
                status_text,
                log_box,
                ft.Button("▶ 开始渲染完整视频", on_click=start_render, width=250, height=50)
            ]),
            padding=20
        )
    )

if __name__ == "__main__":
    ft.run(main)
