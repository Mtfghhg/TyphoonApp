from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button

class TyphoonUI(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', padding=50, spacing=30, **kwargs)
        self.add_widget(Label(text="西北太平洋台风季生成器\n(云端原生版)", font_size=32, halign='center'))
        self.status_label = Label(text="系统就绪", font_size=20)
        self.add_widget(self.status_label)
        btn = Button(text="▶ 开始渲染视频", font_size=28, background_color=(0.1, 0.5, 1, 1))
        btn.bind(on_press=self.start_render)
        self.add_widget(btn)
    def start_render(self, instance):
        self.status_label.text = "正在调用底层引擎渲染...\n(请勿退出)"
class TyphoonApp(App):
    def build(self):
        self.title = '台风视频生成器'
        return TyphoonUI()
if __name__ == '__main__':
    TyphoonApp().run()
