[app]
title = Typhoon Sim
package.name = typhoonsim
package.domain = org.typhoon
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ogg,json
version = 1.0

# 核心修复 1：只保留 arm64-v8a（绝大多数现代手机都是这个架构，减少一半编译量和出错率）
requirements = python3,kivy,pygame,numpy
orientation = landscape
fullscreen = 1
android.permissions = INTERNET, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE

# 核心修复 2：锁定一个老旧但极其稳定的 NDK 和 API 版本
android.archs = arm64-v8a
android.ndk = 25b
android.api = 30
android.minapi = 24
android.accept_sdk_license = True

# 核心修复 3：给 p4a 增加减少编译依赖的参数
p4a.branch = master
p4a.bootstrap = sdl2
