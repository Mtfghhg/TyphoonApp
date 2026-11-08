[app]
title = Typhoon Sim
package.name = typhoonsim
package.domain = org.typhoon
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ogg,json
version = 1.0

requirements = python3,kivy
orientation = landscape
fullscreen = 1
android.permissions = INTERNET, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE
android.archs = arm64-v8a
android.accept_sdk_license = True
android.ndk = 25b

# 【终极防弹衣 1】：强制使用稳定的 p4a 源码分支
p4a.fork = kivy
p4a.branch = master

# 【终极防弹衣 2】：限制单线程编译，绝对不爆内存！
p4a.extra_args = --jobs=1
