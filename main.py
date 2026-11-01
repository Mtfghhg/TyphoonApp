import flet as ft
import cv2
import numpy as np

def main(page: ft.Page):
    page.title = "台风视频生成器"
    
    def start(e):
        page.add(ft.Text("OpenCV 已启动！"))
        
    page.add(
        ft.Text("台风生成器"),
        ft.ElevatedButton("开始渲染", on_click=start)
    )

ft.app(target=main)
