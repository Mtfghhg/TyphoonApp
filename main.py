import flet as ft
import cv2
import numpy as np

def main(page: ft.Page):
    page.title = "台风视频生成器"
    
    # 状态文字（直接用颜色代码，防止不同版本报错）
    status = ft.Text("系统就绪，等待渲染", size=16, color="green")
    
    def start_render(e):
        status.value = "正在调用 OpenCV 引擎...\n(请勿退出)"
        status.color = "orange"
        page.update()
        
        try:
            # 测试 OpenCV 是否正常工作
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            cv2.putText(img, "OK", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            status.value = "✅ OpenCV 渲染成功！\n功能完整，没有阉割！"
            status.color = "green"
        except Exception as ex:
            status.value = f"渲染失败: {ex}"
            status.color = "red"
            
        page.update()

    # 构建界面
    page.add(
        ft.Text("西北太平洋台风季生成器", size=24, weight=ft.FontWeight.BOLD),
        ft.Text("(Flet 云端原生版)", size=14, color="grey"),
        ft.Divider(),
        status,
        ft.Button("▶ 开始渲染视频", on_click=start_render, width=200, height=50)
    )

# 兼容 Flet 1.0+ 的终极启动代码
if __name__ == "__main__":
    ft.run(main)
