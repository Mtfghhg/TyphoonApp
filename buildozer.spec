[app]
title = Typhoon Sim
package.name = typhoonsim
package.domain = org.typhoon
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ogg,json
version = 1.0

# 1. 坚决只写 python3，千万别写版本号！加上 pygame（你的代码需要它）
requirements = python3,kivy,pygame

orientation = landscape
fullscreen = 1
android.permissions = INTERNET, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE
android.archs = arm64-v8a
android.accept_sdk_license = True
android.ndk = 25b

log_level = 1

# 2. 使用 p4a 的 develop 分支，它比 master 更稳定
p4a.fork = kivy
p4a.branch = develop

# 3. 【核心魔法】：强制 pip 遇到 charset-normalizer 时，只许编译源码，不准下载预编译的烂轮子！
p4a.extra_args = --jobs=1 --no-binary charset-normalizer
