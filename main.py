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
    except: pass
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

# ================= 核心引擎 2：颜色与渲染 =================
def get_color(vmax):
    if vmax < 34: return (255, 200, 0)
    if vmax < 64: return (0, 255, 0)
    if vmax < 83: return (0, 255, 255)
    if vmax < 113: return (0, 0, 255)
    return (255, 0, 255)

def render_logic(update_ui):
    try:
        # ⚠️ 请确保这些文件真实存在你手机里
        bdeck_file = "/storage/emulated/0/DCIM/MyAlbums/台风/bwp012024.dat"
        bg_path = "/storage/emulated/0/DCIM/MyAlbums/台风/WPAC.png"
        icon_path = "/storage/emulated/0/DCIM/MyAlbums/台风/N-TC-C5.mp4"
        out_path = "/storage/emulated/0/DCIM/MyAlbums/台风/final_output.mp4"

        update_ui("正在解析 B-deck 数据...", "orange")
        records = parse_bdeck(bdeck_file)
        if len(records) < 2:
            update_ui("❌ B-deck 数据不足，请检查文件路径或格式", "red")
            return

        update_ui(f"解析成功，共 {len(records)} 条记录。开始渲染...", "orange")

        bg = cv2.imread(bg_path)
        bg = cv2.resize(bg, (1080, 1920))
        h, w = bg.shape[:2]

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(out_path, fourcc, 30.0, (w, h))
        cap_icon = cv2.VideoCapture(icon_path)

        total_frames = 300
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

            # 画路径
            for i in range(len(records) - 1):
                if records[i]['time'] > current_t: break
                pt1 = (int((records[i]['lon'] - 100) / 80 * w), int((50 - records[i]['lat']) / 50 * h))
                pt2 = (int((records[i+1]['lon'] - 100) / 80 * w), int((50 - records[i+1]['lat']) / 50 * h))
                cv2.line(frame, pt1, pt2, get_color(records[i]['vmax']), 5)

            # 贴动态图标
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

            # 画 UI (时间轴、ACE、总结条)
            pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            draw = ImageDraw.Draw(pil_img)
            
            draw.rectangle([(30, 30), (450, 80)], fill=(0, 0, 0)) # 时间轴背景
            draw.text((40, 40), f"UTC: {current_t.strftime('%Y-%m-%d %H:%M')}", fill=(255, 255, 255))
            
            draw.rectangle([(w-250, 30), (w-30, 80)], fill=(0, 0, 0)) # ACE背景
            draw.text((w-230, 40), f"ACE: {ace_total:.2f}", fill=(255, 255, 0))

            if frame_idx > total_frames - 90: # 总结条
                draw.rectangle([(50, h-300), (w-50, h-50)], fill=(0, 0, 0))
                draw.text((80, h-260), f"Storm: WP012024", fill=(255, 255, 255))
                draw.text((80, h-210), f"Peak Wind: {max([r['vmax'] for r in records])} kt", fill=(255, 255, 255))
                draw.text((80, h-160), f"Total ACE: {ace_total:.4f}", fill=(255, 255, 255))

            frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            out.write(frame)

        cap_icon.release()
        out.release()
        update_ui(f"✅ 渲染完成！\n已输出到相册: final_output.mp4", "green")

    except Exception as e:
        update_ui(f"❌ 渲染失败: {e}", "red")

# ================= Flet 界面 =================
def main(page: ft.Page):
    page.title = "台风视频生成器 - 完全体"
    page.theme_mode = ft.ThemeMode.DARK

    status_text = ft.Text("系统就绪，请确保素材在指定路径。", size=14, color="green")
    log_box = ft.TextField(multiline=True, read_only=True, height=150)

    def update_ui(msg, color):
        log_box.value += msg + "\n"
        status_text.value = msg
        status_text.color = color
        page.update()

    def start_render(e):
        log_box.value = "开始渲染任务...\n"
        page.update()
        threading.Thread(target=render_logic, args=(update_ui,)).start()

    # 🚨 终极修复：用绝对不会报错的方式画边框！
    box_style = ft.Container(
        padding=10,
        border=ft.Border(
            top=ft.BorderSide(1, "grey"), 
            right=ft.BorderSide(1, "grey"), 
            bottom=ft.BorderSide(1, "grey"), 
            left=ft.BorderSide(1, "grey")
        ),
        border_radius=5
    )

    page.add(
        ft.Container(
            content=ft.Column([
                ft.Text("西北太平洋台风季生成器 (完全体)", size=22, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                box_style(content=ft.Column([
                    ft.Text("数据源", weight=ft.FontWeight.BOLD),
                    ft.Text("B-deck: /storage/emulated/0/DCIM/MyAlbums/台风/bwp012024.dat"),
                    ft.Text("底图: /storage/emulated/0/DCIM/MyAlbums/台风/WPAC.png"),
                    ft.Text("图标: /storage/emulated/0/DCIM/MyAlbums/台风/N-TC-C5.mp4"),
                ])),
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
