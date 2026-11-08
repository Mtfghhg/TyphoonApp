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

# 👇 新增这一行，强制自动同意许可协议
android.accept_sdk_license = True
