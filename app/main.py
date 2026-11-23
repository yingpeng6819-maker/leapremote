# -*- coding: utf-8 -*-
"""零跑控车 App（独立运行版）——基于 markoceri/leapmotor-api 的非官方客户端。

界面：Kivy；网络请求在后台线程执行，避免卡住 UI。
证书：certs/app.crt 与 certs/app.key 随包附带（来自 leapmotor-certs 仓库）。
"""
import json
import os
import threading
import traceback
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.textinput import TextInput

from leapmotor_api import LeapmotorApiClient
from leapmotor_api.exceptions import LeapmotorApiError, LeapmotorAuthError

BASE_DIR = Path(__file__).resolve().parent


def _find_cert(name: str) -> str:
    """依次在源码目录、运行目录、用户目录下查找证书，兼容打包与桌面运行。"""
    candidates = [
        BASE_DIR / "certs" / name,
        Path(os.getcwd()) / "certs" / name,
        BASE_DIR / name,
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return str(candidates[0])


CERT_CRT = _find_cert("app.crt")
CERT_KEY = _find_cert("app.key")


def load_config(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(path: Path, data: dict) -> None:
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


class StatusBar(Label):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.size_hint_y = None
        self.height = dp(34)
        self.color = (1, 0.9, 0.4, 1)
        self.font_size = dp(14)


class LeapApp(App):
    def build(self):
        self.title = "零跑控车"
        self.cfg_path = Path(self.user_data_dir) / "config.json"
        self.cfg = load_config(self.cfg_path)
        self.client = None
        self.vehicle = None
        self.status = None

        self.root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        self._build_login()
        return self.root

    # ------------------------------------------------------------------ UI
    def _clear(self):
        self.root.clear_widgets()

    def _status_bar(self, text, color=(1, 0.9, 0.4, 1)):
        bar = StatusBar(text=text)
        bar.color = color
        self.root.add_widget(bar)

    def _build_login(self):
        self._clear()
        box = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12))
        box.add_widget(Label(text="零跑云端账号登录", font_size=dp(20), bold=True,
                             size_hint_y=None, height=dp(40), color=(0.9, 0.9, 0.9, 1)))

        self.in_user = TextInput(hint_text="账号（邮箱 / 手机号）", multiline=False,
                                 text=self.cfg.get("username", ""), size_hint_y=None, height=dp(44))
        self.in_pass = TextInput(hint_text="密码", multiline=False, password=True,
                                 text=self.cfg.get("password", ""), size_hint_y=None, height=dp(44))
        self.in_pin = TextInput(hint_text="车辆 PIN（远程控车需要，可留空）", multiline=False,
                                password=True, text=self.cfg.get("pin", ""),
                                size_hint_y=None, height=dp(44))
        for w in (self.in_user, self.in_pass, self.in_pin):
            box.add_widget(w)

        btn = Button(text="登 录", size_hint_y=None, height=dp(48), background_color=(0.15, 0.55, 0.9, 1))
        btn.bind(on_press=self._do_login)
        box.add_widget(btn)

        self.login_msg = Label(text="提示：非官方工具，仅用于个人自用。", size_hint_y=None,
                               height=dp(30), color=(0.6, 0.6, 0.6, 1), font_size=dp(12))
        box.add_widget(self.login_msg)
        self.root.add_widget(box)

    def _build_main(self):
        self._clear()

        # 顶部状态摘要
        summary = Label(text="正在刷新车辆状态…", size_hint_y=None, height=dp(120),
                        font_size=dp(15), color=(0.9, 0.95, 1, 1), valign="middle", halign="center")
        summary.bind(size=lambda *_: setattr(summary, "text_size", (summary.width, None)))
        self.summary_label = summary
        self.root.add_widget(summary)

        # 按钮区（可滚动）
        scroll = ScrollView()
        grid = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, padding=dp(4))
        grid.bind(minimum_height=grid.setter("height"))
        self.grid = grid
        scroll.add_widget(grid)
        self.root.add_widget(scroll)

        # 底部操作栏
        bottom = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        for label, cb, color in (
            ("刷新状态", self._refresh_status, (0.2, 0.6, 0.3, 1)),
            ("退出登录", self._logout, (0.6, 0.3, 0.3, 1)),
        ):
            b = Button(text=label, background_color=color)
            b.bind(on_press=cb)
            bottom.add_widget(b)
        self.root.add_widget(bottom)

        self._refresh_status()

    # ------------------------------------------------------------- 后台线程
    def _async(self, fn, on_done=None, on_fail=None):
        def worker():
            try:
                res = fn()
                if on_done:
                    Clock.schedule_once(lambda dt: on_done(res))
            except Exception as e:  # noqa: BLE001
                msg = f"{type(e).__name__}: {e}"
                traceback.print_exc()
                if on_fail:
                    Clock.schedule_once(lambda dt: on_fail(msg))
        threading.Thread(target=worker, daemon=True).start()

    # ---------------------------------------------------------------- 登录
    def _do_login(self, *_):
        username = self.in_user.text.strip()
        password = self.in_pass.text
        pin = self.in_pin.text.strip()
        if not username or not password:
            self.login_msg.text = "请填写账号和密码"
            return
        self.login_msg.text = "登录中…"
        self.cfg.update({"username": username, "password": password, "pin": pin})
        save_config(self.cfg_path, self.cfg)

        def build():
            client = LeapmotorApiClient(
                username=username,
                password=password,
                app_cert_path=CERT_CRT,
                app_key_path=CERT_KEY,
                operation_password=pin or None,
                language="zh-CN",
            )
            client.login()
            vehicles = client.get_vehicle_list()
            if not vehicles:
                raise RuntimeError("账号下没有车辆")
            return client, vehicles[0]

        def ok(res):
            self.client, self.vehicle = res
            self._build_main()

        def fail(msg):
            self.login_msg.text = "登录失败：" + msg

        self._async(build, ok, fail)

    def _logout(self, *_):
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
            self.client = None
        self._build_login()

    # ---------------------------------------------------------------- 状态
    def _refresh_status(self, *_):
        if not self.client or not self.vehicle:
            return
        self.summary_label.text = "正在刷新…"

        def fetch():
            return self.client.get_vehicle_status(self.vehicle)

        def ok(st):
            self.status = st
            self._render_status()
            self._render_buttons()

        def fail(msg):
            self.summary_label.text = "刷新失败：" + msg

        self._async(fetch, ok, fail)

    def _render_status(self):
        s = self.status
        b = s.battery
        c = s.climate
        lines = []
        nick = self.vehicle.vehicle_nickname or self.vehicle.car_type or self.vehicle.vin[-6:]
        lines.append(f"车辆：{nick}")
        soc = b.soc if b.soc is not None else "—"
        mileage = b.expected_mileage if b.expected_mileage is not None else "—"
        charge = "充电中" if s.is_charging else ("已插枪" if s.is_plugged else "未插枪")
        kw = f" {b.charging_power_kw:.1f}kW" if b.charging_power_kw else ""
        lines.append(f"电量 {soc}%  续航 {mileage}km  {charge}{kw}")
        ac = "开" if c.ac_switch else "关"
        lines.append(f"空调 {ac}  车内 {c.interior_temp}℃  车外 {c.outdoor_temp}℃  设定 {c.ac_setting}℃")
        lock = "已锁" if s.is_locked else "未锁"
        lines.append(f"门锁：{lock}")
        bar = s.tire_pressure_bar or {}
        tp = " ".join(f"{k}:{v:.2f}" if isinstance(v, (int, float)) else f"{k}:—"
                      for k, v in bar.items())
        lines.append(f"胎压(bar) {tp}")
        self.summary_label.text = "\n".join(lines)

    def _render_buttons(self):
        g = self.grid
        g.clear_widgets()

        def section(title):
            lbl = Label(text=title, bold=True, size_hint_y=None, height=dp(30),
                        color=(0.6, 0.8, 1, 1), font_size=dp(15))
            g.add_widget(lbl)
            # 占满第二列
            g.add_widget(Label(size_hint_y=None, height=dp(30)))

        def btn(text, action, color=(0.25, 0.25, 0.25, 1)):
            b = Button(text=text, size_hint_y=None, height=dp(46), background_color=color)
            b.bind(on_press=lambda *_: self._run_cmd(action, b))
            g.add_widget(b)

        section("车辆安全")
        btn("锁车", lambda: self.client.lock_vehicle(self.vehicle.vin), (0.7, 0.25, 0.25, 1))
        btn("解锁", lambda: self.client.unlock_vehicle(self.vehicle.vin), (0.2, 0.6, 0.3, 1))
        btn("开后备箱", lambda: self.client.open_trunk(self.vehicle.vin))
        btn("寻车鸣笛", lambda: self.client.find_vehicle(self.vehicle.vin), (0.8, 0.6, 0.2, 1))

        section("空调舒适")
        btn("空调开", lambda: self.client.ac_on(self.vehicle.vin), (0.2, 0.5, 0.8, 1))
        btn("空调关", lambda: self.client.ac_off(self.vehicle.vin))
        btn("快速降温", lambda: self.client.quick_cool(self.vehicle.vin), (0.2, 0.6, 0.9, 1))
        btn("快速升温", lambda: self.client.quick_heat(self.vehicle.vin), (0.9, 0.4, 0.2, 1))
        btn("前挡除霜", lambda: self.client.windshield_defrost(self.vehicle.vin))
        btn("方向盘加热开", lambda: self.client.steering_wheel_heat_on(self.vehicle.vin))
        btn("方向盘加热关", lambda: self.client.steering_wheel_heat_off(self.vehicle.vin))

        section("车窗 / 天窗")
        btn("开车窗", lambda: self.client.open_windows(self.vehicle.vin))
        btn("关车窗", lambda: self.client.close_windows(self.vehicle.vin))
        btn("开天窗", lambda: self.client.open_sunroof(self.vehicle.vin))
        btn("关天窗", lambda: self.client.close_sunroof(self.vehicle.vin))
        btn("开遮阳帘", lambda: self.client.open_sunshade(self.vehicle.vin))
        btn("关遮阳帘", lambda: self.client.close_sunshade(self.vehicle.vin))

        section("充电控制")
        btn("开始充电", lambda: self.client.start_charging(self.vehicle.vin), (0.2, 0.7, 0.4, 1))
        btn("停止充电", lambda: self.client.stop_charging(self.vehicle.vin), (0.7, 0.3, 0.2, 1))
        btn("解锁充电口", lambda: self.client.unlock_charger(self.vehicle.vin))
        btn("充电上限80%", lambda: self.client.set_charge_limit(self.vehicle.vin, 80))

        section("其他")
        btn("电池预热", lambda: self.client.battery_preheat(self.vehicle.vin))
        btn("取消电池预热", lambda: self.client.battery_preheat_off(self.vehicle.vin))
        btn("哨兵模式开", lambda: self.client.sentry_mode_on(self.vehicle.vin))
        btn("哨兵模式关", lambda: self.client.sentry_mode_off(self.vehicle.vin))

    def _run_cmd(self, action, button):
        old = button.text
        button.text = "执行中…"
        button.disabled = True

        def done(_):
            button.text = old
            button.disabled = False
            self._refresh_status()

        def fail(msg):
            button.text = old
            button.disabled = False
            self.summary_label.text = "操作失败：" + msg

        self._async(action, done, fail)


if __name__ == "__main__":
    LeapApp().run()
