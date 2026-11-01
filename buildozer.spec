[app]
title = 台风视频生成器
package.name = typhoonapp
package.domain = org.typhoon
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0
# 【核心修复】锁死 Python 3.10.11，防止死循环
requirements = python3==3.10.11,kivy==2.3.0,opencv,pillow,numpy
orientation = landscape
fullscreen = 0

[buildozer]
log_level = 2
warn_on_root = 1
