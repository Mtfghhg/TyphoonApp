[app]
title = 台风视频生成器
package.name = typhoonapp
package.domain = org.typhoon
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0
# 【核心修复】去掉版本号，让系统自己选最稳定兼容的 Python
requirements = python3,kivy,opencv,pillow,numpy
orientation = landscape
fullscreen = 0

[buildozer]
log_level = 2
warn_on_root = 1
