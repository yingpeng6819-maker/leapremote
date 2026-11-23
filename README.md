# 零跑控车（安卓独立 APK）

基于非官方库 [markoceri/leapmotor-api](https://github.com/markoceri/leapmotor-api) 做的 **Kivy 安卓 App**。
APK 在手机本地运行，不依赖你自己的服务器，点开登录零跑账号即可查看车辆状态、远程控车。

> ⚠️ **风险提示**
> - 这是社区逆向产物，**非零跑官方**，接口变更可能失效。
> - 账号密码会保存在本机（`user_data_dir/config.json`），不要在公用手机上保存。
> - 建议在官方 App 里建一个**共享小号**把车分享给它，避免主账号被挤下线或触发云端临时锁定。
> - 远程控车（锁车/解锁/鸣笛等）需要填写**车辆 PIN**。
> - 本工程遵循上游 AGPL-3.0 协议。

---

## 目录结构

```
leapmotor-app/
├── app/
│   ├── main.py              # Kivy 界面 + 控车逻辑
│   ├── leapmotor_api/       # 内置的 API 库源码（已随包，无需联网安装）
│   └── certs/
│       ├── app.crt          # mTLS 客户端证书（来自 leapmotor-certs）
│       └── app.key          # 客户端私钥
├── buildozer.spec           # 安卓打包配置
├── requirements.txt         # 仅桌面预览用
└── .github/workflows/build-apk.yml   # GitHub Actions 自动出包
```

---

## 方式一：GitHub Actions 自动出 APK（最省事，推荐）

不需要本地装安卓 SDK，云端自动编译。

1. 把整个 `leapmotor-app` 文件夹上传到一个新的 GitHub 仓库（或 fork 后覆盖）。
2. 打开仓库上方 **Actions** 标签 → 左侧 **构建零跑控车 APK** → 点 **Run workflow**。
3. 等 15~30 分钟（首次要下载 SDK/NDK，较慢）。
4. 任务完成后点进去，在底部 **Artifacts** 下载 `leapremote-debug-apk`，解压得到 `.apk`。
5. 传到手机安装（需允许“安装未知来源应用”）。

> 想手动触发：push 到 `main` 也会自动构建。

---

## 方式二：本地 WSL / Ubuntu 出包

需要 Ubuntu（WSL2 即可），首次同样要下载 SDK/NDK：

```bash
# 安装系统依赖
sudo apt-get update
sudo apt-get install -y autoconf libtool pkg-config zlib1g-dev libncurses5-dev \
  libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev openjdk-17-jdk-headless

pip install buildozer cython==0.29.37

# 在 leapmotor-app 目录下执行
buildozer android debug
```

产物在 `bin/` 目录下，文件名形如 `leapremote-1.0.0-debug.apk`。

---

## 桌面预览（Windows / Mac / Linux，先看界面）

```bash
pip install -r requirements.txt
cd app
python main.py
```

桌面预览能看界面和交互，但**真实联网登录需要手机或正常网络环境**。

---

## 使用说明

1. 打开 App，填零跑账号（邮箱/手机号）、密码；远程控车填**车辆 PIN**。
2. 登录后顶部显示：电量、续航、充电状态、空调、门锁、胎压。
3. 按钮分组：
   - **车辆安全**：锁车 / 解锁 / 开后备箱 / 寻车鸣笛
   - **空调舒适**：空调开关、快速降温/升温、前挡除霜、方向盘加热
   - **车窗天窗**：开窗/关窗、天窗、遮阳帘
   - **充电控制**：开始/停止充电、解锁充电口、充电上限 80%
   - **其他**：电池预热、哨兵模式
4. 每次操作后自动刷新状态；失败会在顶部红字提示原因。

---

## 常见问题

- **登录失败 / 账号被锁**：换共享小号；确认密码正确；别短时间反复登录。
- **提示证书缺失**：确认 `app/certs/app.crt`、`app.key` 在包里（buildozer.spec 已配置）。
- **某按钮无反应**：该车型可能不支持此功能，或账号无对应远程权限（云端会拒绝）。
- **想加功能**：可在 `app/main.py` 的 `_render_buttons` 里照葫芦画瓢新增按钮，调用 `self.client` 的对应方法。
