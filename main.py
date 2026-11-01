import flet as ft
import cv2
import numpy as np
import threading
import os

def get_color(vmax):
    # 根据风速返回 BGR 颜色
    if vmax < 34: return (255, 200, 0)
    if vmax < 64: return (0, 255, 0)
    if vmax < 83: return (0, 255, 255)
    if vmax < 113: return (0, 0, 255)
    return (255, 0, 255)

def main(page: ft.Page):
    page.title = "完全体台风生成器"
    page.theme_mode = ft.ThemeMode.DARK
    
    status_text = ft.Text("系统就绪", size=16, color="green")
    progress_ring = ft.ProgressRing(visible=False)

    def update_ui(msg, color):
        status_text.value = msg
        status_text.color = color
        progress_ring.visible = False
        page.update()

    def render_video():
        try:
            base_dir = "/storage/emulated/0/DCIM/MyAlbums/台风/"
            bg_path = os.path.join(base_dir, "WPAC.png")
            icon_path = os.path.join(base_dir, "N-TC-C5.mp4")
            out_path = os.path.join(base_dir, "true_typhoon_video.mp4")

            if not os.path.exists(bg_path):
                update_ui("❌ 找不到底图，权限被拦截", "red")
                return

            # 准备底图
            bg = cv2.imread(bg_path)
            bg = cv2.resize(bg, (1280, 720))
            h, w = bg.shape[:2]

            # 准备视频写入器 (设置帧率 30，编码器 mp4v)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(out_path, fourcc, 30.0, (w, h))

            # 提取你的专属动态图标
            cap_icon = cv2.VideoCapture(icon_path)
            
            # 模拟台风路径数据 (从屏幕左下角往右上角移动)
            path_points = [(150, 600, 30), (300, 500, 50), (500, 400, 80), (800, 300, 120), (1000, 150, 90)]
            
            # 开始循环画 150 帧 (大概 5 秒视频)
            for frame_idx in range(150):
                frame = bg.copy()
                
                # 1. 绘制带颜色的拖尾路径 (随着时间推移，线越来越长)
                current_step = int((frame_idx / 150) * len(path_points))
                for i in range(1, current_step):
                    pt1 = (path_points[i-1][0], path_points[i-1][1])
                    pt2 = (path_points[i][0], path_points[i][1])
                    color = get_color(path_points[i][2])
                    cv2.line(frame, pt1, pt2, color, 5)
                
                # 2. 获取图标视频的当前帧
                ret, icon_frame = cap_icon.read()
                if not ret:
                    cap_icon.set(cv2.CAP_PROP_POS_FRAMES, 0) # 循环播放
                    ret, icon_frame = cap_icon.read()
                    
                # 3. 把图标贴在路径的最后一个点上
                if ret and current_step > 0:
                    icon_frame = cv2.resize(icon_frame, (100, 100))
                    cx, cy = path_points[current_step-1][0], path_points[current_step-1][1]
                    top, left = max(0, cy-50), max(0, cx-50)
                    bot, right = min(h, top+100), min(w, left+100)
                    # 滤色叠加
                    roi = frame[top:bot, left:right]
                    ic = icon_frame[0:bot-top, 0:right-left]
                    frame[top:bot, left:right] = cv2.addWeighted(roi, 0.5, ic, 0.5, 0)

                # 4. 【加功能】在左上角画一个模拟的时间轴 UI
                time_str = f"Day {frame_idx // 30 + 1} - 12:00 UTC"
                cv2.putText(frame, time_str, (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                
                # 5. 【加功能】模拟 ACE 数值
                ace_val = frame_idx * 0.15
                cv2.putText(frame, f"ACE: {ace_val:.2f}", (1100, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

                # 写入这一帧
                out.write(frame)

            cap_icon.release()
            out.release()
            update_ui(f"✅ 视频生成成功！已保存至相册: true_typhoon_video.mp4", "green")

        except Exception as e:
            update_ui(f"❌ 渲染失败: {e}", "red")

    def start_click(e):
        status_text.value = "正在逐帧生成 MP4 视频，请耐心等待..."
        status_text.color = "orange"
        progress_ring.visible = True
        page.update()
        # 开启后台线程
        threading.Thread(target=render_video).start()

    page.add(
        ft.Text("台风视频生成器 (全功能版)", size=24, weight=ft.FontWeight.BOLD),
        ft.Row([progress_ring, status_text]),
        ft.Button("▶ 生成完整 MP4 视频", on_click=start_click, width=250, height=50)
    )

if __name__ == "__main__":
    ft.run(main)
