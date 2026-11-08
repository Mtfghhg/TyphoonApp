[app]
title = Typhoon Sim
package.name = typhoonsim
package.domain = org.typhoon
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ogg,json
version = 1.0
requirements = python3,kivy,pygame,numpy
orientation = landscape
fullscreen = 1
android.permissions = INTERNET, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE

# 只编译一个架构，减轻负担
android.archs = arm64-v8a
# 同意协议
android.accept_sdk_license = True
# 锁定稳定的 NDK 版本
android.ndk = 25b
