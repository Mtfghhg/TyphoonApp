[app]
title = Typhoon Sim
package.name = typhoonsim
package.domain = org.typhoon
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ogg,json
version = 1.0

# 【核心保送 1】：强行锁死 Python 版本为 3.10，绝对不用坑爹的 3.14！
# 【核心保送 2】：强行指定使用旧版的 charset-normalizer，避开新版的恶心 Bug！
requirements = python3==3.10.11,kivy,charset-normalizer==3.3.2

orientation = landscape
fullscreen = 1
android.permissions = INTERNET, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE
android.archs = arm64-v8a
android.accept_sdk_license = True
android.ndk = 25b

log_level = 1
p4a.fork = kivy
p4a.branch = master
p4a.extra_args = --jobs=1
