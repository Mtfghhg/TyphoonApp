[app]
title = F13 Typhoon
package.name = f13typhoon
package.domain = org.f13

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ogg,json
version = 1.0

# 核心：把需要的库全装上
requirements = python3,kivy,numpy,opencv,pillow

orientation = landscape
fullscreen = 1
android.archs = arm64-v8a
android.accept_sdk_license = True
android.ndk = 25b
p4a.branch = master
