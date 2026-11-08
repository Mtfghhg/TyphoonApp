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

# 核心修复 1：只编译 arm64 架构，减轻负担
android.archs = arm64-v8a
android.accept_sdk_license = True

# 核心修复 2：强制指定使用系统环境，并锁定稳定的 NDK 和 Build-Tools
android.sdk_path = /usr/local/lib/android/sdk
android.ndk_path = /usr/local/lib/android/sdk/ndk/25.1.8937393
android.build_tools_version = 30.0.3

# 核心修复 3：强制要求 Python for Android 的稳定分支
p4a.branch = master
