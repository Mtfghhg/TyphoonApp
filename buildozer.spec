[app]
title = Typhoon Sim V1.4.4
package.name = typhoonsim
package.domain = org.typhoon
source.dir = .
# 加上字体和所有可能的媒体格式
source.include_exts = py,png,jpg,kv,atlas,ogg,json,ttf,ttc,otf
source.include_patterns = assets/*, map/*, py/*, font/*, *.json

version = 1.4.4
requirements = python3,kivy,pygame
orientation = landscape
fullscreen = 1
android.permissions = INTERNET, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE
android.archs = arm64-v8a
android.accept_sdk_license = True
android.ndk = 25b

log_level = 1
p4a.fork = kivy
p4a.branch = develop
# 依然保持单线程，防止 600MB 编译时爆内存
p4a.extra_args = --jobs=1
