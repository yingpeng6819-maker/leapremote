[app]
# 应用基本信息
title = 零跑控车
package.name = leapremote
package.domain = org.selfuse

# 源码目录（app/ 内含 main.py 与 vendor 的 leapmotor_api）
source.dir = app
source.include_exts = py,pem,key,crt,json
# 把证书目录随包打进 APK
source.include_files = app/certs

version = 1.0.0

# 依赖：python3 + kivy 界面 + requests 网络 + cryptography(mTLS/签名) + pillow
requirements = python3, kivy, requests, cryptography, pillow

# 启动入口（source.dir=app 后，main.py 在导入路径顶层）
android.entrypoint = main:LeapApp

# 应用需要联网访问零跑云端
android.permissions = INTERNET, ACCESS_NETWORK_STATE, ACCESS_WIFI_STATE

# 横竖屏：跟随手机
android.orientation = portrait

# 关闭全屏状态栏隐藏（便于看时间）
android.fullscreen = 0

# SDK / NDK（CI 与本地由 buildozer 自动下载，一般无需改）
android.api = 34
android.ndk = 25b
android.sdk = 24

# 构建配置
android.accept_sdk_license = True
android.enable_androidx = True

# 日志
log_level = info

[buildozer]
log_level = 2
warn_on_root = 1
