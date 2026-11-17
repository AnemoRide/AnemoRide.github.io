# -*- coding: utf-8 -*-
"""
相机参数全能工具箱 v3.0
================================================================
纯标准库、零依赖的命令行相机计算器。

覆盖 8 大类 / 48 项计算：
  10 画幅·视场·采样     11-18
  20 景深·对焦           21-27
  30 曝光                31-37
  40 闪光·照明           41-45
  50 视频·数据           51-56
  60 天文·航拍           61-70
  70 打印·色彩·画质      71-75

防呆设计：
  * 输入自动识别 1/125、2s、35mm、10m、ND1000、全角数字、带千分位等写法；
  * 传感器从预设表选，手打时若高 > 宽会自动纠正；
  * 每个参数都有合理区间，越界立即提示「上限/下限」并重输；
  * 任意输入处键入 q 即可放弃本次计算，Ctrl+C / EOF 不会把程序搞崩；
  * 启动即打印参考表（传感器规格、档位序列、焦距视角、色温、场景 EV）。

记录：所有结果按时间戳追加到脚本同目录的「相机计算记录.txt」。

运行：python Camera_tools_v2.py
自检：python Camera_tools_v2.py --selftest
"""

from __future__ import annotations

import math
import os
import sys
import time
import unicodedata

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, "相机计算记录.txt")

INF = float("inf")

# ======================= 基础常量与预设 =======================
FF_W, FF_H = 36.0, 24.0
FF_DIAG = math.hypot(FF_W, FF_H)
FF_COC = 0.030
COC_DIV = 1500.0          # 现代数码常用：对角线 / 1500

# (名称, 宽 mm, 高 mm, 常见用途)
SENSORS = [
    ("1/3.2\" 手机",      4.54,   3.42, "前置 / 入门手机"),
    ("1/2.3\"",          6.17,   4.55, "卡片机 / 无人机"),
    ("1/1.7\"",          7.60,   5.70, "高端卡片机"),
    ("1/1.3\"",          9.60,   7.20, "大底手机"),
    ("1\"",             13.20,   8.80, "RX100 / Mavic 3"),
    ("M4/3",            17.30,  13.00, "M4/3 系统"),
    ("APS-C 佳能",      22.30,  14.90, "1.6x"),
    ("APS-C 索/尼/富",   23.50,  15.60, "1.5x"),
    ("APS-H",           27.90,  18.60, "1.3x，老 1D"),
    ("全画幅 36x24",     36.00,  24.00, "1.0x"),
    ("4433 中画幅",      44.00,  33.00, "GFX / X1D"),
    ("645 中画幅",       53.00,  40.00, "X2D / IQ4"),
    ("6x6 中画幅",       56.00,  56.00, "老式中画幅"),
    ("4x5 大画幅",      127.00, 101.60, "4x5 英寸"),
]
DEFAULT_SENSOR = next(i for i, s in enumerate(SENSORS) if "全画幅" in s[0])

F_NUMS = [1.0, 1.2, 1.4, 1.8, 2.0, 2.8, 3.5, 4.0, 5.6, 8.0, 11.0, 16.0, 22.0, 32.0]
ISO_STEPS = [100, 200, 400, 800, 1600, 3200, 6400, 12800, 25600]
SHUTTER_STEPS = ["1/1000", "1/500", "1/250", "1/125", "1/60", "1/30", "1/15",
                 "1/8", "1/4", "1/2", "1s", "2s", "4s", "8s", "15s", "30s"]
ND_TABLE = [("ND2", 1), ("ND4", 2), ("ND8", 3), ("ND16", 4), ("ND32", 5),
            ("ND64", 6), ("ND100", 6.6), ("ND400", 8.6), ("ND1000", 10),
            ("ND2000", 11), ("ND10000", 13.3)]
WB_TABLE = [("烛光 / 火光", 1900), ("白炽灯", 2800), ("暖白 LED", 3200),
            ("日出日落", 3500), ("摄影棚钨丝灯", 3400), ("荧光灯", 4000),
            ("日光（正午）", 5500), ("阴天", 6500), ("蓝调时刻", 7500),
            ("晴天阴影", 8000), ("高原 / 雪地", 9000)]
EV_SCENE = [(3, "烛光夜景"), (5, "城市夜景"), (7, "室内弱光"),
            (9, "室内正常照明"), (11, "阴天室外"), (12, "多云"),
            (13, "晴天阴影"), (14, "晴天顺光"), (15, "雪地 / 沙滩"),
            (16, "极亮反光面")]
FF_FOCALS = [8, 12, 14, 16, 18, 20, 24, 28, 35, 40, 50, 60, 70, 85, 100,
             105, 135, 150, 180, 200, 300, 400, 500, 600, 800]
FOCAL_USE = {
    14: "超广 / 星空 / 建筑", 16: "超广", 20: "广角风光", 24: "广角 / 环境人像",
    28: "人文 / 街拍", 35: "人文纪实", 50: "标准", 85: "人像", 100: "微距 / 人像",
    135: "压缩感人像", 200: "长焦", 300: "野生 / 运动", 400: "远摄",
    500: "打鸟", 600: "打鸟 / 天文", 800: "极远摄",
}

# ======================= 输出工具 =======================
def dw(text) -> int:
    """按东亚字符宽度计算显示宽度，保证表格对齐。"""
    total = 0
    for ch in str(text):
        total += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return total


def pad(text, width: int, align: str = "left") -> str:
    text = str(text)
    gap = width - dw(text)
    if gap <= 0:
        return text
    if align == "right":
        return " " * gap + text
    if align == "center":
        left = gap // 2
        return " " * left + text + " " * (gap - left)
    return text + " " * gap


def table(headers, rows, aligns=None, indent: str = "  ") -> str:
    cols = len(headers)
    aligns = list(aligns) if aligns else ["left"] * cols
    cells = [[str(c) for c in r] for r in rows]
    widths = [dw(h) for h in headers]
    for r in cells:
        for i in range(min(cols, len(r))):
            widths[i] = max(widths[i], dw(r[i]))

    lines = [indent + "  ".join(pad(headers[i], widths[i], "center") for i in range(cols))]
    lines.append(indent + "  ".join("─" * widths[i] for i in range(cols)))
    for r in cells:
        cols_txt = [pad(r[i] if i < len(r) else "", widths[i], aligns[i]) for i in range(cols)]
        lines.append(indent + "  ".join(cols_txt))
    return "\n".join(lines)


def kv(rows, indent: str = "  ") -> str:
    if not rows:
        return ""
    width = max(dw(k) for k, _ in rows)
    return "\n".join(f"{indent}{pad(k, width)} : {v}" for k, v in rows)


def head(title: str) -> str:
    return "\n" + "─" * 64 + f"\n  {title}\n" + "─" * 64


def fmt_shutter(t: float) -> str:
    if t == INF:
        return "∞"
    if t >= 60:
        return f"{t / 60:.1f} min"
    if t >= 1:
        return f"{t:.1f} s"
    denom = 1.0 / t
    if denom < 2:
        return f"{t * 1000:.0f} ms"
    if denom < 1000:
        return f"1/{denom:.0f}"
    return f"{t * 1000:.2f} ms"


def fmt_mm(x: float) -> str:
    if x == INF:
        return "∞"
    if abs(x) >= 1000:
        return f"{x / 1000:.2f} m"
    return f"{x:.1f} mm"


def finish(text: str) -> None:
    print(text)
    log_result(text)


def log_result(text: str) -> None:
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fp:
            fp.write("\n" + "=" * 64 + "\n")
            fp.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}]\n")
            fp.write(text.strip() + "\n")
    except OSError:
        pass


# ======================= 输入工具（防呆核心） =======================
class UserCancel(Exception):
    """用户在输入处键入 q / Ctrl+C / EOF。"""


_FULLWIDTH = {ord(c): ord("0") + i for i, c in enumerate("０１２３４５６７８９")}
_FULLWIDTH.update({
    ord("．"): ord("."), ord("／"): ord("/"), ord("－"): ord("-"),
    ord("："): ord(":"), ord("，"): ord(","), ord("％"): ord("%"),
    ord("　"): ord(" "), ord("。"): ord("."), ord("＋"): ord("+"),
    ord("　"): ord(" "),
})


def norm(text) -> str:
    return str(text).translate(_FULLWIDTH).strip()


def _num(token: str) -> float:
    token = token.strip()
    if "/" in token:
        a, b = token.split("/", 1)
        if float(b) == 0:
            raise ValueError("分母为 0")
        return float(a) / float(b)
    return float(token)


LEN_UNITS = (("毫米", 1.0), ("mm", 1.0), ("厘米", 10.0), ("cm", 10.0),
             ("英寸", 25.4), ("inch", 25.4), ("in", 25.4), ("\"", 25.4))


def parse_len_mm(text) -> float:
    """解析长度并统一换算为 mm。支持 36 / 36mm / 3.6cm / 1.4in。"""
    t = norm(text).replace(" ", "").replace(",", "")
    low = t.lower()
    for unit, mul in LEN_UNITS:
        if low.endswith(unit):
            return _num(t[: -len(unit)]) * mul
    return _num(t)


DIST_UNITS = (("毫米", 0.001), ("mm", 0.001), ("厘米", 0.01), ("cm", 0.01),
              ("千米", 1000.0), ("km", 1000.0), ("米", 1.0), ("m", 1.0))


def parse_dist_m(text) -> float:
    """解析距离并统一换算为 m。支持 10 / 10m / 500cm / 3km。"""
    t = norm(text).replace(" ", "").replace(",", "")
    low = t.lower()
    for unit, mul in DIST_UNITS:
        if low.endswith(unit):
            return _num(t[: -len(unit)]) * mul
    return _num(t)


def parse_shutter(text) -> float:
    """解析快门为秒。支持 1/125、0.008、8ms、2s、1/2.5。"""
    t = norm(text).replace(" ", "").replace(",", "").replace("秒", "")
    low = t.lower()
    if low.endswith("ms"):
        return _num(t[:-2]) / 1000.0
    if low.endswith("s"):
        return _num(t[:-1])
    return _num(t)


def parse_len_cm(text) -> float:
    """解析长度并统一换算为 cm（用于柔光箱、成品尺寸这类 cm 口径）。"""
    return parse_len_mm(text) / 10.0


def parse_nd(text) -> float:
    """解析 ND 倍数：ND1000 / nd1000 / 1000 都行。"""
    t = norm(text).replace(" ", "").lower().replace("倍", "")
    if t.startswith("nd"):
        t = t[2:]
    return _num(t)


def _read(prompt: str) -> str:
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        print()
        raise UserCancel()


def ask_num(prompt, lo=None, hi=None, default=None, unit="", parse=None,
            hint="") -> float:
    """通用数值输入：带默认值、区间校验、单位、q 取消。"""
    parse = parse or _num
    label = f"{prompt}({unit})" if unit else prompt
    tail = f" [{default:g}]" if isinstance(default, (int, float)) else ""
    extra = f"  {hint}" if hint else ""
    while True:
        raw = _read(f"  {label}{tail}：")
        token = norm(raw).lower()
        if token in ("q", "quit", "exit", "退出"):
            raise UserCancel()
        if not token:
            if default is not None:
                return float(default)
            print("  [提示] 这一项必填，直接回车无效（q 取消）")
            continue
        try:
            value = float(parse(token))
        except Exception:
            print(f"  [提示] 看不懂「{raw}」。可写 50、2.8、1/125、35mm、10m 之类{extra}")
            continue
        if math.isnan(value) or math.isinf(value):
            print("  [提示] 数值无效，请重新输入")
            continue
        if lo is not None and value < lo:
            print(f"  [提示] 太小：{value:g}{unit} < 合理下限 {lo:g}{unit}，请重输（q 取消）")
            continue
        if hi is not None and value > hi:
            print(f"  [提示] 太大：{value:g}{unit} > 合理上限 {hi:g}{unit}，请重输（q 取消）")
            continue
        return value


def ask_int(prompt, lo=None, hi=None, default=None, unit="") -> int:
    value = ask_num(prompt, lo, hi, default, unit)
    return int(round(value))


def ask_choice(prompt, options, default=None) -> str:
    """选项选择：可输入编号、键名，或直接回车取默认。"""
    print(f"\n  {prompt}")
    for i, (key, label) in enumerate(options, 1):
        mark = "（默认）" if default is not None and key == default else ""
        print(f"   {i}. {label}{mark}")
    while True:
        raw = _read("  选择编号：")
        token = norm(raw).lower()
        if token in ("q", "quit", "exit", "退出"):
            raise UserCancel()
        if not token:
            if default is not None:
                return default
            print("  [提示] 请选择一个编号（q 取消）")
            continue
        if token.isdigit():
            idx = int(token)
            if 1 <= idx <= len(options):
                return options[idx - 1][0]
        for key, _label in options:
            if token == key.lower():
                return key
        print(f"  [提示] 只接受 1~{len(options)} 的编号，或 {options[0][0]}、{options[-1][0]} 这样的键名")


def ask_yes(prompt, default=False) -> bool:
    tail = "Y/n" if default else "y/N"
    while True:
        raw = _read(f"  {prompt}（{tail}）：")
        token = norm(raw).lower()
        if token in ("q", "quit", "exit", "退出"):
            raise UserCancel()
        if not token:
            return default
        if token in ("y", "yes", "是", "1"):
            return True
        if token in ("n", "no", "否", "0"):
            return False
        print("  [提示] 请回答 y 或 n")


def ask_sensor():
    """选择传感器：输入编号，或 c 自定义宽高。"""
    print("\n  传感器（回车 = 全画幅，c = 自定义）：")
    cols = 4
    for start in range(0, len(SENSORS), cols):
        cells = []
        for i in range(start, min(start + cols, len(SENSORS))):
            cells.append(pad(f"{i + 1} {SENSORS[i][0]}", 18))
        print("   " + "".join(cells).rstrip())
    print(f"   c 自定义尺寸")
    px_default = DEFAULT_SENSOR + 1
    while True:
        raw = _read(f"  选哪个（默认 {px_default}）：")
        token = norm(raw).lower()
        if token in ("q", "quit", "exit", "退出"):
            raise UserCancel()
        if not token:
            idx = px_default
        elif token.isdigit() and 1 <= int(token) <= len(SENSORS):
            idx = int(token)
        elif token in ("c", "custom", "自定义"):
            w = ask_num("自定义传感器宽度", 0.5, 500, 36, "mm", parse=parse_len_mm)
            h = ask_num("自定义传感器高度", 0.5, 500, 24, "mm", parse=parse_len_mm)
            if h > w:
                w, h = h, w
                print(f"  [已纠正] 高度不应大于宽度，已自动交换为 {w:g} × {h:g} mm")
            return w, h, "自定义"
        else:
            print(f"  [提示] 请输入 1~{len(SENSORS)} 的编号，c 自定义，或直接回车")
            continue
        name, w, h, _use = SENSORS[idx - 1]
        return w, h, name


def ask_lens(default_f=50.0):
    """传感器 + 物理焦距，一次性给出常用派生量。"""
    w, h, name = ask_sensor()
    f = ask_num("物理焦距", 0.3, 5000, default_f, "mm", parse=parse_len_mm)
    diag = math.hypot(w, h)
    crop = FF_DIAG / diag
    return {
        "w": w, "h": h, "name": name, "f": f, "diag": diag,
        "crop": crop, "eqf": f * crop,
    }


def ask_pitch(w_mm, default_px=6000):
    """由传感器宽度与横向像素数算出像元间距（um）。"""
    px_w = ask_int("横向像素数", 100, 200000, default_px, "px")
    return w_mm * 1000.0 / px_w, px_w


# ======================= 光学核心公式 =======================
def fov_angles(w, h, f):
    """返回 (水平, 垂直, 对角) 视场角（度）与对角线长度。"""
    diag = math.hypot(w, h)
    fh = 2 * math.degrees(math.atan(w / (2 * f)))
    fv = 2 * math.degrees(math.atan(h / (2 * f)))
    fd = 2 * math.degrees(math.atan(diag / (2 * f)))
    return fh, fv, fd, diag


def crop_factor(w, h):
    return FF_DIAG / math.hypot(w, h)


def coc_of(w, h, divisor=COC_DIV):
    return math.hypot(w, h) / divisor


def hyperfocal_mm(f, n, c):
    return f * f / (n * c) + f


def dof_range(f, n, s_mm, c):
    """返回 (近界 mm, 远界 mm, 超焦距 mm)。"""
    hper = hyperfocal_mm(f, n, c)
    near = s_mm * (hper - f) / (hper + s_mm - 2 * f)
    far = s_mm * (hper - f) / (hper - s_mm) if s_mm < hper else INF
    return near, far, hper


def pixel_pitch_um(w_mm, px_w):
    return w_mm * 1000.0 / px_w


def airy_um(n, lam_um=0.55):
    return 2.44 * lam_um * n


def pixel_angle_deg(pitch_um, f_mm):
    return math.degrees(math.atan((pitch_um / 1000.0) / f_mm))


def ev100(n, t, iso):
    return math.log2(n * n / t) - math.log2(iso / 100.0)


def mired(k):
    return 1_000_000.0 / k


def kelvin(m):
    return 1_000_000.0 / m


def nearest_focal(eqf):
    return min(FF_FOCALS, key=lambda x: abs(x - eqf))


# ======================= 10 · 画幅 / 视场 / 采样 =======================
def m11():
    w, h, name = ask_sensor()
    f = ask_num("物理焦距", 0.3, 5000, 50, "mm", parse=parse_len_mm)
    fh, fv, fd, diag = fov_angles(w, h, f)
    crop = FF_DIAG / diag
    eqf = f * crop
    per_m_w = 2 * math.tan(math.radians(fh / 2))
    per_m_h = 2 * math.tan(math.radians(fv / 2))
    text = head("11 · FOV 正向：焦距 → 视场角")
    text += "\n" + kv([
        ("传感器", f"{w:g} × {h:g} mm（{name}）"),
        ("对角线", f"{diag:.2f} mm"),
        ("物理焦距", f"{f:g} mm"),
        ("裁切系数", f"{crop:.3f} ×"),
        ("等效焦距", f"{eqf:.1f} mm（全画幅视角）"),
        ("水平视场", f"{fh:.2f}°"),
        ("垂直视场", f"{fv:.2f}°"),
        ("对角视场", f"{fd:.2f}°"),
        ("1 m 处画面", f"{per_m_w:.3f} × {per_m_h:.3f} m"),
    ])
    text += "\n  提示：视场角只由「画幅尺寸 / 焦距」决定，与像素多少无关。"
    finish(text)


def m12():
    w, h, name = ask_sensor()
    axis = ask_choice("目标尺寸对应画面哪个方向？",
                      [("w", "宽度（水平）"), ("h", "高度（垂直）"), ("d", "对角线")], "w")
    dist = ask_num("拍摄距离", 0.02, 1_000_000, 10, "m", parse=parse_dist_m)
    target = ask_num("目标物体真实尺寸", 0.001, 100_000, 2, "m", parse=parse_dist_m)
    dim = {"w": w, "h": h, "d": math.hypot(w, h)}[axis]
    f = dim * dist / target
    fh, fv, fd, diag = fov_angles(w, h, f)
    crop = FF_DIAG / diag
    eqf = f * crop
    text = head("12 · FOV 反向：目标尺寸 → 所需焦距")
    text += "\n" + kv([
        ("传感器", f"{w:g} × {h:g} mm（{name}）"),
        ("拍摄距离", f"{dist:g} m"),
        ("目标尺寸", f"{target:g} m（{axis.upper()} 方向铺满画面）"),
        ("所需物理焦距", f"{f:.2f} mm"),
        ("等效焦距", f"{eqf:.1f} mm"),
        ("此时水平视场", f"{fh:.2f}°"),
        ("最接近的常规焦段", f"{nearest_focal(eqf)} mm（等效）"),
    ])
    if eqf < 8:
        text += "\n  [注意] 等效焦距 < 8mm，属于鱼眼/超广范围，普通镜头难以实现。"
    if eqf > 800:
        text += "\n  [注意] 等效焦距 > 800mm，需要长焦 + 增距镜，注意空气扰动。"
    finish(text)


def m13():
    lens = ask_lens(35)
    dist = ask_num("拍摄距离", 0.02, 1_000_000, 5, "m", parse=parse_dist_m)
    fh, fv, fd, _ = fov_angles(lens["w"], lens["h"], lens["f"])
    fw = 2 * dist * math.tan(math.radians(fh / 2))
    fhh = 2 * dist * math.tan(math.radians(fv / 2))
    fdd = 2 * dist * math.tan(math.radians(fd / 2))
    text = head("13 · 画面尺寸：距离 → 拍到多宽")
    text += "\n" + kv([
        ("镜头", f"{lens['f']:g} mm（等效 {lens['eqf']:.0f} mm，{lens['name']}）"),
        ("距离", f"{dist:g} m"),
        ("画面宽度", f"{fw:.2f} m"),
        ("画面高度", f"{fhh:.2f} m"),
        ("画面对角", f"{fdd:.2f} m"),
        ("每 1 m 距离画面宽", f"{2 * math.tan(math.radians(fh / 2)):.4f} m"),
        ("每 1 m 距离画面高", f"{2 * math.tan(math.radians(fv / 2)):.4f} m"),
    ])
    text += "\n  提示：画面尺寸 = 2 × 距离 × tan(视场角 / 2)，与像素、对焦无关。"
    finish(text)


def m14():
    mode = ask_choice("换算方向",
                      [("a", "由传感器求裁切系数 / 等效焦距"),
                       ("b", "已知等效焦距反推物理焦距"),
                       ("c", "两台相机同视角换算")], "a")
    if mode == "c":
        w1, h1, n1 = ask_sensor()
        print("\n  —— 换到另一台相机 ——")
        w2, h2, n2 = ask_sensor()
        f1 = ask_num("第一台相机的物理焦距", 0.3, 5000, 50, "mm", parse=parse_len_mm)
        c1, c2 = crop_factor(w1, h1), crop_factor(w2, h2)
        eqf = f1 * c1
        f2 = eqf / c2
        text = head("14c · 同视角跨机换算")
        text += "\n" + kv([
            ("相机 A", f"{n1}，{w1:g}×{h1:g} mm，裁切 {c1:.2f}"),
            ("相机 B", f"{n2}，{w2:g}×{h2:g} mm，裁切 {c2:.2f}"),
            ("A 的视角等效焦距", f"{f1:g} mm → 等效 {eqf:.1f} mm"),
            ("B 上要同视角", f"需要 {f2:.2f} mm"),
        ])
        finish(text)
        return

    w, h, name = ask_sensor()
    crop = crop_factor(w, h)
    if mode == "a":
        f = ask_num("物理焦距", 0.3, 5000, 50, "mm", parse=parse_len_mm)
        eqf = f * crop
        text = head("14 · 裁切系数 / 等效焦距")
        text += "\n" + kv([
            ("传感器", f"{w:g} × {h:g} mm（{name}）"),
            ("裁切系数", f"{crop:.4f} ×"),
            ("物理焦距", f"{f:g} mm"),
            ("等效全画幅焦距", f"{eqf:.2f} mm"),
            ("等效光圈（同景深）", f"标称 F 值 × {crop:.2f}"),
            ("通光量折损", f"{2 * math.log2(crop):.2f} 档（相对全画幅）"),
        ])
    else:
        eqf = ask_num("想达到的等效焦距", 1, 3000, 50, "mm")
        f = eqf / crop
        text = head("14 · 等效焦距 → 物理焦距")
        text += "\n" + kv([
            ("传感器", f"{w:g} × {h:g} mm（{name}）"),
            ("裁切系数", f"{crop:.4f} ×"),
            ("目标等效焦距", f"{eqf:g} mm"),
            ("所需物理焦距", f"{f:.2f} mm"),
        ])
    text += "\n  提示：裁切系数 = 43.27 mm ÷ 传感器对角线；只影响视角，不改变曝光。"
    finish(text)


def m15():
    w, h, name = ask_sensor()
    px_w = ask_int("横向像素数", 100, 200000, 6000, "px")
    px_h = ask_int("纵向像素数", 100, 200000, 4000, "px")
    aspect_sensor = w / h
    aspect_px = px_w / px_h
    pitch = w * 1000.0 / px_w
    mp = px_w * px_h / 1e6
    text = head("15 · 传感器像素规格：像元间距 / 密度")
    text += "\n" + kv([
        ("传感器", f"{w:g} × {h:g} mm（{name}）"),
        ("像素", f"{px_w} × {px_h} = {mp:.2f} MP"),
        ("像元间距", f"{pitch:.2f} um（{pitch / 1000:.4f} mm）"),
        ("像素密度", f"{1e6 / (pitch ** 2):.1f} 万像素 / cm²"),
        ("传感器面积", f"{w * h / 100:.2f} cm²"),
        ("300 dpi 最大打印", f"{px_w / 300 * 2.54:.1f} × {px_h / 300 * 2.54:.1f} cm"),
        ("200 dpi 最大打印", f"{px_w / 200 * 2.54:.1f} × {px_h / 200 * 2.54:.1f} cm"),
        ("每像素张角（配 50mm）", f"{pixel_angle_deg(pitch, 50) * 3600:.1f} 角秒"),
    ])
    if abs(aspect_sensor - aspect_px) / aspect_sensor > 0.02:
        text += f"\n  [注意] 像素纵横比 {aspect_px:.2f} 与传感器 {aspect_sensor:.2f} 不一致，像元可能不是正方形。"
    finish(text)


def m16():
    lens = ask_lens(50)
    pitch, px_w = ask_pitch(lens["w"], 6000)
    text = head("16 · 衍射极限 DLA 与艾里斑")
    text += "\n" + kv([
        ("传感器 / 焦距", f"{lens['w']:g}×{lens['h']:g} mm，{lens['f']:g} mm"),
        ("像元间距", f"{pitch:.2f} um"),
        ("开始可见软化", f"F{1.49 * pitch:.1f}（艾里斑 ≈ 2 像素）"),
        ("明显损失细节", f"F{2.98 * pitch:.1f}（艾里斑 ≈ 4 像素）"),
        ("建议日常上限", f"F{1.8 * pitch:.1f} 左右"),
    ])
    text += "\n\n  各光圈下的艾里斑："
    rows = []
    for n in [1.4, 2, 2.8, 4, 5.6, 8, 11, 16, 22, 32]:
        a = airy_um(n)
        rows.append([f"F{n:g}", f"{a:.2f}", f"{a / pitch:.2f}",
                     "轻微" if a / pitch < 1.5 else ("可见" if a / pitch < 3 else "明显")])
    text += "\n" + table(["光圈", "艾里斑 um", "占几个像素", "影响"],
                         rows, ["right", "right", "right", "left"])
    text += "\n  提示：绿光 550nm，艾里斑直径 = 2.44 × 波长 × 光圈值。"
    finish(text)


def m17():
    print("\n  —— 原画幅 ——")
    a = ask_lens(50)
    print("\n  —— 目标画幅 ——")
    w2, h2, n2 = ask_sensor()
    n_val = ask_num("原镜头光圈 F 值", 0.5, 128, 2.8, "F")
    iso = ask_num("原 ISO", 6, 409600, 100, "ISO")
    c1, c2 = crop_factor(a["w"], a["h"]), crop_factor(w2, h2)
    ratio = c2 / c1
    text = head("17 · 跨画幅等效：焦距 / 光圈 / 景深")
    text += "\n" + kv([
        ("A 设备", f"{a['name']}，{a['f']:g} mm F{n_val:g} ISO{iso:g}"),
        ("B 设备", f"{n2}，裁切 {c2:.2f}"),
        ("同视角所需焦距", f"{a['f'] * ratio:.2f} mm"),
        ("同景深所需光圈", f"F{n_val * ratio:.2f}"),
        ("同噪点所需 ISO", f"ISO{iso * ratio ** 2:.0f}"),
        ("两者视角是否一致", "一致（等效焦距相同）"),
        ("B 的通光量差", f"{-2 * math.log2(ratio):+.2f} 档"),
    ])
    text += "\n  提示：小画幅要「同视角 + 同景深 + 同噪点」，需要更小的 F 值和更低的 ISO。"
    finish(text)


def m18():
    w, h, name = ask_sensor()
    px_w = ask_int("原图横向像素", 100, 200000, 6000, "px")
    px_h = ask_int("原图纵向像素", 100, 200000, 4000, "px")
    ratio = ask_num("裁切倍率（1.5 = 只剩中间 1/1.5 的线性尺寸）", 1.0, 8.0, 1.5, "x")
    new_mp = (px_w / ratio) * (px_h / ratio) / 1e6
    old_mp = px_w * px_h / 1e6
    f_eq_now = 50 * ratio
    text = head("18 · 裁切后剩余像素与等效焦距")
    text += "\n" + kv([
        ("传感器", f"{w:g} × {h:g} mm（{name}）"),
        ("原始像素", f"{px_w} × {px_h} = {old_mp:.2f} MP"),
        ("裁切倍率", f"{ratio:g} ×"),
        ("裁切后像素", f"{int(px_w / ratio)} × {int(px_h / ratio)} = {new_mp:.2f} MP"),
        ("像素损失", f"{(1 - new_mp / old_mp) * 100:.1f}%"),
        ("视角变化", f"等效焦距 × {ratio:g}（50mm 变 {f_eq_now:.0f}mm 视角）"),
        ("300 dpi 打印", f"{px_w / ratio / 300 * 2.54:.1f} cm 长边"),
    ])
    text += "\n  提示：裁切不增加细节，只是把已有像素放大，噪点与 diffraction 也会被一起放大。"
    finish(text)


# ======================= 20 · 景深 / 对焦 =======================
def m21():
    lens = ask_lens(50)
    n_val = ask_num("光圈 F 值", 0.5, 128, 2.8, "F")
    dist = ask_num("对焦距离", 0.01, 100000, 3, "m", parse=parse_dist_m)
    c = coc_of(lens["w"], lens["h"])
    near, far, hper = dof_range(lens["f"], n_val, dist * 1000.0, c)
    total = (far - near) if far != INF else INF
    text = head("21 · 景深 & 超焦距")
    text += "\n" + kv([
        ("镜头", f"{lens['f']:g} mm F{n_val:g}（{lens['name']}）"),
        ("允许弥散圆", f"{c * 1000:.2f} um（对角线 / {COC_DIV:g}）"),
        ("对焦距离", f"{dist:g} m"),
        ("超焦距", f"{hper / 1000:.2f} m"),
        ("清晰近界", f"{near / 1000:.3f} m"),
        ("清晰远界", "∞" if far == INF else f"{far / 1000:.3f} m"),
        ("总景深", "∞" if total == INF else f"{total / 1000:.3f} m"),
        ("对焦距离 / 超焦距", f"{dist * 1000 / hper * 100:.1f}%"),
    ])
    if dist * 1000 >= hper:
        text += "\n  提示：已超过超焦距，远界为无穷远，此时再远对焦只损失近景。"
    finish(text)


def m22():
    lens = ask_lens(50)
    dist = ask_num("对焦距离", 0.01, 100000, 3, "m", parse=parse_dist_m)
    c = coc_of(lens["w"], lens["h"])
    rows = []
    for n_val in [1.4, 2, 2.8, 4, 5.6, 8, 11, 16, 22]:
        near, far, hper = dof_range(lens["f"], n_val, dist * 1000.0, c)
        total = "∞" if far == INF else f"{(far - near) / 1000:.2f}"
        rows.append([f"F{n_val:g}", f"{hper / 1000:.2f}",
                     f"{near / 1000:.2f}",
                     "∞" if far == INF else f"{far / 1000:.2f}",
                     total if total == "∞" else f"{total} m"])
    text = head(f"22 · 景深表（{lens['f']:g}mm，对焦 {dist:g}m）")
    text += "\n" + table(["光圈", "超焦距 m", "近界 m", "远界 m", "总景深"],
                         rows, ["right", "right", "right", "right", "right"])
    text += f"\n  弥散圆 {c * 1000:.1f} um。光圈每收小一档，景深约增加 √2 倍。"
    finish(text)


def m23():
    lens = ask_lens(24)
    near_want = ask_num("希望从多远开始就清晰", 0.05, 10000, 1, "m", parse=parse_dist_m)
    c = coc_of(lens["w"], lens["h"])
    x_mm = near_want * 1000.0
    n_req = lens["f"] ** 2 / (c * (2 * x_mm - lens["f"]))
    n_pick = min([x for x in F_NUMS if x >= n_req] or [64])
    focus_mm = 2 * x_mm
    near, far, hper = dof_range(lens["f"], n_pick, focus_mm, c)
    text = head("23 · 超焦距对焦（近景到无穷全清晰）")
    text += "\n" + kv([
        ("镜头", f"{lens['f']:g} mm（{lens['name']}）"),
        ("期望近界", f"{near_want:g} m"),
        ("所需光圈（理论）", f"F{n_req:.2f}"),
        ("建议实际光圈", f"F{n_pick:g}"),
        ("对焦距离", f"{focus_mm / 1000:.2f} m（≈ 2 × 近界）"),
        ("实际近界", f"{near / 1000:.2f} m"),
        ("实际远界", "∞" if far == INF else f"{far / 1000:.2f} m"),
        ("超焦距", f"{hper / 1000:.2f} m"),
    ])
    text += "\n  提示：这就是「超焦距对焦法」——对焦到 2 倍近界，光圈收到理论值，近到远景全清晰。"
    finish(text)


def m24():
    lens = ask_lens(100)
    mode = ask_choice("已知哪个量？",
                      [("a", "对焦距离（从传感器平面起算）"),
                       ("b", "工作距离（从镜头前端起算，近似）"),
                       ("c", "已知放大倍率，求拍摄范围")], "a")
    c = coc_of(lens["w"], lens["h"])
    n_val = ask_num("光圈 F 值", 0.5, 128, 5.6, "F")
    if mode == "a":
        u = ask_num("对焦距离", 0.01, 100, 0.5, "m", parse=parse_dist_m) * 1000.0
        if u <= lens["f"]:
            print("  [提示] 对焦距离必须大于焦距，否则无法成像。")
            return
        mag = lens["f"] / (u - lens["f"])
    elif mode == "b":
        wd = ask_num("工作距离", 1, 5000, 300, "mm", parse=parse_len_mm)
        mag = lens["f"] / wd
    else:
        mag = ask_num("放大倍率（1 = 1:1）", 0.01, 20, 1.0, "x")
    fov_w = lens["w"] / mag
    fov_h = lens["h"] / mag
    n_eff = n_val * (1 + mag)
    dof_macro = 2 * n_eff * c * (1 + mag) / (mag * mag)
    text = head("24 · 放大倍率与微距景深")
    text += "\n" + kv([
        ("镜头", f"{lens['f']:g} mm F{n_val:g}"),
        ("放大倍率", f"{mag:.3f} X（1:{(1 / mag):.1f}）"),
        ("画面覆盖范围", f"{fov_w:.2f} × {fov_h:.2f} mm"),
        ("有效光圈", f"F{n_eff:.2f}（近摄光损失 {2 * math.log2(1 + mag):.2f} 档）"),
        ("微距总景深", f"{dof_macro:.2f} mm"),
    ])
    if mode == "b":
        text += "\n  [注意] 工作距离模型是近似：真实倍率还取决于镜头结构（内对焦会缩短有效焦距）。"
    finish(text)


def m25():
    lens = ask_lens(50)
    base_mag = ask_num("镜头原生放大倍率（普通镜头约 0.15）", 0, 10, 0.15, "x")
    ext = ask_num("近摄接圈总长度（没有就填 0）", 0, 300, 0, "mm", parse=parse_len_mm)
    tc = ask_num("增距镜倍率（没有就填 1）", 1, 3, 1, "x")
    n_val = ask_num("光圈 F 值", 0.5, 128, 5.6, "F")
    new_f = lens["f"] * tc
    new_mag = base_mag * tc + ext / new_f
    n_eff = n_val * tc * (1 + new_mag)
    text = head("25 · 近摄接圈 / 增距镜")
    text += "\n" + kv([
        ("原镜头", f"{lens['f']:g} mm F{n_val:g}，原生 {base_mag:g}X"),
        ("加装后焦距", f"{new_f:.1f} mm"),
        ("加装后倍率", f"{new_mag:.3f} X"),
        ("等效光圈", f"F{n_eff:.2f}"),
        ("画面覆盖", f"{lens['w'] / new_mag:.1f} × {lens['h'] / new_mag:.1f} mm"),
        ("对焦距离范围", "接圈会压缩对焦范围，可能无法对无穷远"),
    ])
    text += "\n  提示：接圈加倍率但损失无穷远对焦；增距镜加焦距又放大倍率，代价是光圈与画质。"
    finish(text)


def m26():
    lens = ask_lens(100)
    n_val = ask_num("光圈 F 值", 0.5, 128, 8, "F")
    mag = ask_num("放大倍率（1 = 1:1）", 0.05, 20, 1.0, "x")
    c = coc_of(lens["w"], lens["h"])
    overlap = ask_num("重叠率（建议 0.6~0.8）", 0.1, 0.95, 0.7, "")
    depth = ask_num("需要覆盖的景深", 0.1, 500, 20, "mm", parse=parse_len_mm)
    n_eff = n_val * (1 + mag)
    single = 2 * n_eff * c * (1 + mag) / (mag * mag)
    step = single * (1 - overlap)
    shots = math.ceil(depth / step) + 1
    text = head("26 · 焦点堆栈步进")
    text += "\n" + kv([
        ("镜头 / 倍率", f"{lens['f']:g} mm，{mag:g}X，F{n_val:g}"),
        ("单张景深", f"{single:.3f} mm"),
        ("建议步进", f"{step:.3f} mm（重叠 {overlap * 100:.0f}%）"),
        ("覆盖需求", f"{depth:g} mm"),
        ("建议张数", f"{shots} 张（含首尾余量 +1）"),
        ("总位移", f"{step * (shots - 1):.1f} mm"),
    ])
    text += "\n  提示：步进太大会出现「条带」，宁多拍勿少拍；用微距滑轨按步进手推最稳。"
    finish(text)


def m27():
    lens = ask_lens(50)
    pitch, _px = ask_pitch(lens["w"], 6000)
    shake = ask_num("手抖角速度（普通人约 0.3~1.0 度/秒）", 0.01, 20, 0.5, "°/s")
    ibis = ask_num("机身/镜头防抖补偿（没有填 0）", 0, 8, 0, "档")
    t_rule = 1.0 / lens["eqf"]
    angle_px = pixel_angle_deg(pitch, lens["f"])
    t_pixel = angle_px / shake
    text = head("27 · 安全快门与手抖拖影")
    text += "\n" + kv([
        ("镜头", f"{lens['f']:g} mm（等效 {lens['eqf']:.0f} mm）"),
        ("像元间距", f"{pitch:.2f} um，单像素张角 {angle_px * 3600:.1f} 角秒"),
        ("1/等效焦距 法则", f"{fmt_shutter(t_rule)}"),
        ("像素级安全快门", f"{fmt_shutter(t_pixel)}（拖影 < 1 像素）"),
        (f"开 {ibis:g} 档防抖后", f"{fmt_shutter(t_pixel * 2 ** ibis)}"),
        ("建议实拍快门", f"{fmt_shutter(min(t_rule, t_pixel))} 或更快"),
    ])
    text += "\n  提示：像素越高，同样的抖动会占更多像素，所以高像素机要更快的快门。"
    finish(text)


# ======================= 30 · 曝光 =======================
def m31():
    mode = ask_choice("要求解哪个量？",
                      [("a", "已知 F / 快门 / ISO，求 EV"),
                       ("b", "已知 EV / F / 快门，求所需 ISO"),
                       ("c", "已知 EV / ISO / 快门，求所需光圈"),
                       ("d", "已知 EV / F / ISO，求所需快门")], "a")
    if mode == "a":
        n_val = ask_num("光圈 F 值", 0.5, 128, 8, "F")
        t = ask_num("快门", 5e-6, 7200, 1 / 125, "s", parse=parse_shutter,
                    hint="可写 1/125 或 2s")
        iso = ask_num("ISO", 6, 409600, 100, "ISO")
        ev = ev100(n_val, t, iso)
        scene = min(EV_SCENE, key=lambda x: abs(x[0] - ev))[1]
        text = head("31 · EV 曝光计算")
        text += "\n" + kv([
            ("曝光组合", f"F{n_val:g}，{fmt_shutter(t)}，ISO{iso:g}"),
            ("EV（以 ISO100 计）", f"{ev:.2f}"),
            ("对应场景", scene),
            ("建议", "EV 越大场景越亮，需要更快的快门或更小的光圈"),
        ])
    elif mode == "b":
        ev = ask_num("目标 EV100", -8, 22, 14, "EV")
        n_val = ask_num("光圈 F 值", 0.5, 128, 8, "F")
        t = ask_num("快门", 5e-6, 7200, 1 / 125, "s", parse=parse_shutter)
        iso = n_val ** 2 / (t * 2 ** ev) * 100
        text = head("31b · 求所需 ISO")
        text += "\n" + kv([
            ("目标 EV100", f"{ev:.2f}"),
            ("光圈 / 快门", f"F{n_val:g}，{fmt_shutter(t)}"),
            ("所需 ISO", f"{iso:.0f}"),
        ])
        if iso > 51200:
            text += "\n  [注意] 需要的 ISO 过高，画质会明显下降，建议补光或放慢快门。"
    elif mode == "c":
        ev = ask_num("目标 EV100", -8, 22, 14, "EV")
        iso = ask_num("ISO", 6, 409600, 100, "ISO")
        t = ask_num("快门", 5e-6, 7200, 1 / 125, "s", parse=parse_shutter)
        n_val = math.sqrt(2 ** ev * t * (iso / 100.0))
        text = head("31c · 求所需光圈")
        text += "\n" + kv([("目标 EV100", f"{ev:.2f}"),
                           ("ISO / 快门", f"ISO{iso:g}，{fmt_shutter(t)}"),
                           ("所需光圈", f"F{n_val:.2f}")])
    else:
        ev = ask_num("目标 EV100", -8, 22, 14, "EV")
        n_val = ask_num("光圈 F 值", 0.5, 128, 8, "F")
        iso = ask_num("ISO", 6, 409600, 100, "ISO")
        t = n_val ** 2 / ((iso / 100.0) * 2 ** ev)
        text = head("31d · 求所需快门")
        text += "\n" + kv([("目标 EV100", f"{ev:.2f}"),
                           ("光圈 / ISO", f"F{n_val:g}，ISO{iso:g}"),
                           ("所需快门", fmt_shutter(t))])
        if t > 30:
            text += "\n  [注意] 超过 30s，需要 B 门与快门线，并考虑长曝噪点与互易律。"
    finish(text)


def m32():
    ev = ask_num("目标 EV100", -6, 20, 12, "EV")
    isos = [100, 400, 1600, 6400]
    rows = []
    for n_val in [1.4, 2, 2.8, 4, 5.6, 8, 11, 16]:
        row = [f"F{n_val:g}"]
        for iso in isos:
            t = n_val ** 2 / ((iso / 100.0) * 2 ** ev)
            row.append(fmt_shutter(t))
        rows.append(row)
    text = head(f"32 · 曝光等值组合表（EV{ev:g}）")
    text += "\n" + table(["光圈"] + [f"ISO {s}" for s in isos], rows,
                         ["left", "right", "right", "right", "right"])
    text += "\n  提示：表内任一组合曝光量相同，区别在景深、动态模糊与噪点。"
    finish(text)


def m33():
    print("\n  —— 组合 A（基准）——")
    na = ask_num("A 光圈", 0.5, 128, 8, "F")
    ta = ask_num("A 快门", 5e-6, 7200, 1 / 125, "s", parse=parse_shutter)
    iso_a = ask_num("A ISO", 6, 409600, 100, "ISO")
    print("\n  —— 组合 B ——")
    nb = ask_num("B 光圈", 0.5, 128, 2.8, "F")
    tb = ask_num("B 快门", 5e-6, 7200, 1 / 1000, "s", parse=parse_shutter)
    iso_b = ask_num("B ISO", 6, 409600, 400, "ISO")
    delta = math.log2((nb ** 2) * ta / (na ** 2 * tb)) - math.log2(iso_b / iso_a)
    text = head("33 · 两组曝光差几档")
    text += "\n" + kv([
        ("A", f"F{na:g}，{fmt_shutter(ta)}，ISO{iso_a:g}"),
        ("B", f"F{nb:g}，{fmt_shutter(tb)}，ISO{iso_b:g}"),
        ("EV 差", f"{delta:+.2f} 档"),
        ("含义", "B 更亮" if delta > 0 else ("B 更暗" if delta < 0 else "完全等价")),
        ("换算成 ND", f"ND{2 ** abs(delta):.1f}" if abs(delta) > 0.05 else "无差异"),
    ])
    finish(text)


def m34():
    base = ask_num("不加滤镜时的快门", 5e-6, 7200, 1 / 125, "s", parse=parse_shutter)
    mode = ask_choice("按哪种方式输入减光量？",
                      [("a", "减光档数（10 档 = ND1024）"),
                       ("b", "ND 倍数（ND1000 这种写法）")], "a")
    if mode == "a":
        stops = ask_num("减光档数", 0, 20, 10, "档")
    else:
        nd_x = ask_num("ND 倍数（ND1000 就填 1000）", 1, 2_000_000, 1000, "倍",
                       parse=parse_nd)
        stops = math.log2(nd_x)
    new_t = base * 2 ** stops
    text = head("34 · ND 滤镜与长曝时间")
    text += "\n" + kv([
        ("基础快门", fmt_shutter(base)),
        ("减光量", f"{stops:.2f} 档（ND{2 ** stops:.0f}）"),
        ("加滤镜后快门", fmt_shutter(new_t)),
        ("等效", f"{new_t:.2f} s" if new_t < 60 else f"{new_t / 60:.2f} min"),
        ("是否需要 B 门", "是（超过 30s）" if new_t > 30 else "否"),
        ("常见 ND 如 ND8 / ND64 / ND1000", "3 / 6 / 10 档"),
    ])
    text += "\n  提示：两片 ND 叠加时档数相加；叠 CPL 约再减 1~1.5 档。"
    finish(text)


def m35():
    nominal = ask_num("测光给出的快门", 0.5, 7200, 8, "s", parse=parse_shutter)
    kind = ask_choice("介质", [("d", "数码（一般无需补偿）"), ("f", "胶片（互易律失效）")], "d")
    if kind == "f":
        if nominal < 1:
            comp = 0.0
            note = "1s 以内基本无需补偿"
        elif nominal < 4:
            comp = 1 / 3
            note = "+1/3 档"
        elif nominal < 16:
            comp = 0.5
            note = "+1/2 档"
        elif nominal < 60:
            comp = 1.0
            note = "+1 档"
        elif nominal < 240:
            comp = 1.5
            note = "+1.5 档"
        else:
            comp = 2.0
            note = "+2 档起，需实测"
    else:
        comp = 0.0
        note = "数码传感器线性较好，长曝主要靠降噪，不需补偿"
    actual = nominal * 2 ** comp
    text = head("35 · 长曝互易律补偿")
    text += "\n" + kv([
        ("测光快门", fmt_shutter(nominal)),
        ("介质", "数码" if kind == "d" else "胶片"),
        ("补偿量", f"{comp:+.2f} 档（{note}）"),
        ("实际应给", fmt_shutter(actual)),
        ("实际秒数", f"{actual:.2f} s"),
    ])
    text += "\n  提示：胶片互易律因乳剂而异，此处为经验区间，重要拍摄请包围测试。"
    finish(text)


def m36():
    lens = ask_lens(50)
    pitch, _px = ask_pitch(lens["w"], 6000)
    speed = ask_num("被摄体移动速度", 0.001, 2000, 1, "m/s")
    dist = ask_num("拍摄距离", 0.05, 2000, 10, "m", parse=parse_dist_m)
    t = ask_num("曝光时间", 5e-6, 60, 1 / 500, "s", parse=parse_shutter)
    blur_px = speed * t * lens["f"] * 1000.0 / (dist * pitch)
    t1 = dist * pitch / (speed * lens["f"] * 1000.0)
    t2 = 2 * dist * pitch / (speed * lens["f"] * 1000.0)
    ang_speed = math.degrees(math.atan(speed / dist))
    text = head("36 · 运动模糊 / 摇拍")
    text += "\n" + kv([
        ("镜头 / 像元", f"{lens['f']:g} mm，{pitch:.2f} um"),
        ("速度 / 距离", f"{speed:g} m/s，{dist:g} m"),
        ("曝光时间", fmt_shutter(t)),
        ("模糊长度", f"{blur_px:.2f} 像素"),
        ("控制在 1 像素内", fmt_shutter(t1)),
        ("控制在 2 像素内", fmt_shutter(t2)),
        ("摇拍匹配角速度", f"{ang_speed:.2f} °/s（相机需同步转动）"),
    ])
    if blur_px > 2:
        text += "\n  [建议] 当前拖影明显：缩短快门、提高 ISO，或改用闪光凝固。"
    finish(text)


def m37():
    base = ask_num("基准快门", 5e-6, 7200, 1 / 125, "s", parse=parse_shutter)
    comp = ask_num("曝光补偿（+ 更亮 / - 更暗）", -5, 5, 0, "EV")
    new_t = base * 2 ** comp
    count = ask_int("包围曝光张数", 1, 9, 3, "张")
    step = ask_num("包围步长", 0.1, 5, 1, "档")
    list_t = []
    half = count // 2
    for i in range(count):
        offset = (i - half) * step
        list_t.append(fmt_shutter(new_t * 2 ** offset))
    text = head("37 · 曝光补偿与包围曝光")
    text += "\n" + kv([
        ("基准快门", fmt_shutter(base)),
        ("补偿", f"{comp:+g} EV"),
        ("补偿后快门", fmt_shutter(new_t)),
        ("包围设置", f"{count} 张，步长 {step:g} 档"),
        ("各张快门", "  |  ".join(list_t)),
    ])
    text += "\n  提示：+EV = 更亮 = 更慢快门 / 更大光圈 / 更高 ISO，三者等效。"
    finish(text)


# ======================= 40 · 闪光 / 照明 =======================
def m41():
    n_val = ask_num("光圈 F 值", 0.5, 128, 5.6, "F")
    iso = ask_num("ISO", 6, 409600, 100, "ISO")
    dist = ask_num("闪光灯到被摄体距离", 0.05, 500, 3, "m", parse=parse_dist_m)
    gn_need = n_val * dist * math.sqrt(iso / 100.0)
    gn100_full = ask_num("灯的 GN（ISO100、全功率，未知填 60）", 1, 200, 60, "GN")
    power_ratio = (gn_need / gn100_full) ** 2
    stops_down = -math.log2(power_ratio) if power_ratio > 0 else 0
    text = head("41 · 闪光灯 GN：需要多大灯")
    text += "\n" + kv([
        ("曝光需求", f"F{n_val:g}，ISO{iso:g}，距离 {dist:g} m"),
        ("所需 GN", f"{gn_need:.1f}（在 ISO{iso:g} 下）"),
        ("折算到 ISO100", f"{gn_need / math.sqrt(iso / 100.0):.1f}"),
        ("若灯 GN100 = ", f"{gn100_full:g}"),
        ("所需功率", f"{power_ratio * 100:.1f}%（约 {stops_down:+.1f} 档）"),
        ("结论", "功率够" if power_ratio <= 1 else "功率不足，需提高 ISO 或靠近"),
    ])
    text += "\n  提示：GN = 光圈 × 距离（ISO100）；ISO 翻倍，GN 乘 √2。"
    finish(text)


def m42():
    gn100 = ask_num("灯的 GN（ISO100 全功率）", 1, 300, 60, "GN")
    iso = ask_num("拍摄 ISO", 6, 409600, 100, "ISO")
    mode = ask_choice("已知什么？",
                      [("a", "已知光圈，求最大距离"), ("b", "已知距离，求可用光圈")], "a")
    gn_eff = gn100 * math.sqrt(iso / 100.0)
    if mode == "a":
        n_val = ask_num("光圈 F 值", 0.5, 128, 5.6, "F")
        d_max = gn_eff / n_val
        text = head("42 · GN 反算：这盏灯能打多远")
        text += "\n" + kv([("灯 GN100 / 当前 ISO", f"{gn100:g} / {iso:g}"),
                           ("当前有效 GN", f"{gn_eff:.1f}"),
                           ("光圈", f"F{n_val:g}"),
                           ("最大距离", f"{d_max:.2f} m")])
        text += "\n\n  不同光圈下的最大距离："
        rows = [[f"F{x:g}", f"{gn_eff / x:.2f}"] for x in [1.4, 2, 2.8, 4, 5.6, 8, 11]]
        text += "\n" + table(["光圈", "距离 m"], rows, ["right", "right"])
    else:
        dist = ask_num("距离", 0.05, 500, 3, "m", parse=parse_dist_m)
        n_use = gn_eff / dist
        text = head("42 · GN 反算：该用多大光圈")
        text += "\n" + kv([("灯 GN100 / 当前 ISO", f"{gn100:g} / {iso:g}"),
                           ("距离", f"{dist:g} m"),
                           ("可用光圈", f"F{n_use:.2f}"),
                           ("整档取用", f"F{min([x for x in F_NUMS if x >= n_use] or [32]):g}")])
    finish(text)


def m43():
    gn100 = ask_num("全功率 GN（ISO100）", 1, 300, 60, "GN")
    n_val = ask_num("光圈 F 值", 0.5, 128, 5.6, "F")
    hss_loss = ask_num("高速同步损失（一般 1.5~2.5 档）", 0, 5, 2, "档")
    rows = []
    for label, ev_loss in [("1/1", 0), ("1/2", 1), ("1/4", 2), ("1/8", 3),
                           ("1/16", 4), ("1/32", 5), ("1/64", 6), ("1/128", 7)]:
        gn = gn100 * 2 ** (-ev_loss / 2)
        rows.append([label, f"-{ev_loss}", f"{gn:.1f}", f"{gn / n_val:.2f}"])
    text = head("43 · 闪光功率档位表")
    text += "\n" + table(["功率档", "相对损失", "有效 GN", f"F{n_val:g} 最大距离 m"],
                         rows, ["left", "right", "right", "right"])
    text += f"\n\n  高速同步（HSS）按损失 {hss_loss:g} 档折算："
    text += f" 有效 GN ≈ {gn100 * 2 ** (-hss_loss / 2):.1f}，F{n_val:g} 下约 {gn100 * 2 ** (-hss_loss / 2) / n_val:.2f} m"
    text += "\n  提示：功率每减一档，GN 变为 1/√2，照射距离缩短约 29%。"
    finish(text)


def m44():
    d1 = ask_num("原距离", 0.05, 500, 2, "m", parse=parse_dist_m)
    d2 = ask_num("新距离", 0.05, 500, 4, "m", parse=parse_dist_m)
    delta = 2 * math.log2(d2 / d1)
    box = ask_num("柔光箱边长（圆形填直径）", 5, 500, 90, "cm", parse=parse_len_cm)
    box_dist = ask_num("柔光箱到被摄体距离", 5, 2000, 100, "cm", parse=parse_len_cm)
    ratio = box / box_dist
    if ratio >= 1.0:
        quality = "极柔（几乎没有边缘阴影）"
    elif ratio >= 0.5:
        quality = "柔光"
    elif ratio >= 0.25:
        quality = "中性偏柔"
    else:
        quality = "硬光（边缘锐利、阴影明显）"
    text = head("44 · 平方反比与柔光光质")
    text += "\n" + kv([
        ("距离变化", f"{d1:g} m → {d2:g} m"),
        ("光量变化", f"{-delta:+.2f} 档（{2 ** (-delta) * 100:.1f}%）"),
        ("柔光箱 / 距离", f"{box:.0f} cm / {box_dist:.0f} cm = {ratio:.2f}"),
        ("光质判断", quality),
        ("建议比值", "人像 0.5~1.0；轮廓光 0.2~0.3"),
    ])
    text += "\n  提示：光源相对面积越大，过渡越柔；平方反比让距离翻倍时曝光减 2 档。"
    finish(text)


def m45():
    t_flash = ask_num("闪光持续时间 t0.5", 1e-6, 0.1, 1 / 2000, "s", parse=parse_shutter,
                      hint="低功率可到 1/10000")
    speed = ask_num("被摄体速度", 0.001, 200, 0.5, "m/s")
    dist = ask_num("拍摄距离", 0.05, 100, 2, "m", parse=parse_dist_m)
    lens = ask_lens(85)
    pitch, _px = ask_pitch(lens["w"], 6000)
    blur_px = speed * t_flash * lens["f"] * 1000.0 / (dist * pitch)
    text = head("45 · 闪光凝固能力")
    text += "\n" + kv([
        ("闪光 t0.5", fmt_shutter(t_flash)),
        ("速度 / 距离", f"{speed:g} m/s，{dist:g} m"),
        ("镜头 / 像元", f"{lens['f']:g} mm，{pitch:.2f} um"),
        ("拖影长度", f"{blur_px:.2f} 像素"),
        ("结论", "凝固良好" if blur_px <= 1 else ("轻微拖影" if blur_px <= 2.5 else "会糊")),
    ])
    text += "\n  提示：凝固靠的是闪光持续时间，不是快门速度；功率越低闪得越短。"
    finish(text)


# ======================= 50 · 视频 / 数据 =======================
def m51():
    mode = ask_choice("换算方向",
                      [("a", "帧率 + 快门角度 → 快门速度"),
                       ("b", "帧率 + 快门速度 → 快门角度")], "a")
    fps = ask_num("帧率", 1, 480, 25, "fps")
    if mode == "a":
        angle = ask_num("快门角度", 0.5, 360, 180, "°")
        t = angle / (360.0 * fps)
        text = head("51 · 快门角度 → 快门速度")
        text += "\n" + kv([
            ("帧率", f"{fps:g} fps"),
            ("快门角度", f"{angle:g}°"),
            ("快门速度", fmt_shutter(t)),
            ("曝光占空比", f"{angle / 360 * 100:.0f}%"),
        ])
    else:
        t = ask_num("快门速度", 5e-6, 1, 1 / 50, "s", parse=parse_shutter)
        angle = 360.0 * fps * t
        text = head("51 · 快门速度 → 快门角度")
        text += "\n" + kv([("帧率", f"{fps:g} fps"),
                           ("快门", fmt_shutter(t)),
                           ("等效快门角度", f"{angle:.1f}°")])
    rows = []
    for a in [360, 270, 180, 144, 90, 45]:
        rows.append([f"{a}°", fmt_shutter(a / (360.0 * fps)), f"{a / 360 * 100:.0f}%"])
    text += "\n\n  常用角度对照："
    text += "\n" + table(["角度", "快门", "占空比"], rows, ["right", "right", "right"])
    text += f"\n  提示：180° 是电影感基准；低于 90° 画面生硬，360° 会明显拖影。"
    finish(text)


def m52():
    bitrate = ask_num("录制码率", 1, 10000, 100, "Mbps")
    cap = ask_num("存储卡容量", 1, 4000, 128, "GB")
    minutes = cap * 8000.0 / bitrate / 60.0
    text = head("52 · 录制时长估算")
    text += "\n" + kv([
        ("码率", f"{bitrate:g} Mbps"),
        ("容量", f"{cap:g} GB"),
        ("可录时长", f"{minutes:.0f} 分钟（{minutes / 60:.1f} 小时）"),
        ("每分钟占用", f"{bitrate * 60 / 8 / 1000:.2f} GB"),
        ("折算", f"{bitrate / 8:.1f} MB/s"),
    ])
    text += "\n  提示：实际可用容量约 90%（文件系统与预留空间），4K 高码率务必留余量。"
    finish(text)


def m53():
    rec = ask_num("拍摄帧率（升格）", 1, 1000, 120, "fps")
    play = ask_num("播放帧率（时间线）", 1, 240, 24, "fps")
    real = ask_num("素材实际时长", 0.1, 600, 5, "s")
    slow_factor = rec / play
    text = head("53 · 升格 / 慢动作换算")
    text += "\n" + kv([
        ("拍摄 / 播放帧率", f"{rec:g} → {play:g} fps"),
        ("慢放倍数", f"{slow_factor:.1f} ×"),
        ("素材 {:.1f}s".format(real), f"成片 {real * slow_factor:.1f} s"),
        ("想剪出 10s 成片", f"需实拍 {10 / slow_factor:.2f} s"),
    ])
    text += "\n  提示：升格不录音（多数机器），且高帧率常伴随裁切与码率上升。"
    finish(text)


def m54():
    interval = ask_num("拍摄间隔", 0.1, 3600, 5, "s")
    total_min = ask_num("总拍摄时长", 1, 24 * 60, 60, "min")
    fps = ask_num("输出帧率", 1, 120, 30, "fps")
    frames = int(total_min * 60 / interval)
    clip = frames / fps
    text = head("54 · 延时摄影")
    text += "\n" + kv([
        ("间隔 / 总时长", f"{interval:g}s / {total_min:g}min"),
        ("总张数", f"{frames} 张"),
        ("成片时长（{:.0f}fps）".format(fps), f"{clip:.1f} s"),
        ("等效加速", f"{clip / (total_min * 60):.1f} × 实时"),
        ("成片秒数需求反推", f"想要 30s 成片需 {30 * fps} 张"),
    ])
    text += "\n  提示：快门建议 ≤ 间隔的 1/2，避免间隔被写入卡时间吃掉；日转夜要留曝光渐变。"
    finish(text)


def m55():
    px_w = ask_int("横向像素", 100, 200000, 6000, "px")
    px_h = ask_int("纵向像素", 100, 200000, 4000, "px")
    bits = ask_num("位深", 8, 32, 14, "bit")
    ratio = ask_num("压缩比（无压缩填 1）", 0.05, 20, 1, "x")
    raw_mb = px_w * px_h * bits / 8 / 1024 ** 2
    mb = raw_mb / ratio
    text = head("55 · 文件体积估算")
    text += "\n" + kv([
        ("像素", f"{px_w} × {px_h} = {px_w * px_h / 1e6:.1f} MP"),
        ("位深 / 压缩", f"{bits:g} bit，{ratio:g}:1"),
        ("未压缩", f"{raw_mb:.1f} MB"),
        ("估算体积", f"{mb:.1f} MB"),
        ("128GB 卡可存", f"{128 * 1000 / mb:.0f} 张"),
    ])
    text += "\n  提示：14bit 通常装在 16bit 容器里，所以未压缩 RAW ≈ 2 字节/像素。"
    finish(text)


def m56():
    cap_mah = ask_num("电池容量", 100, 20000, 2000, "mAh")
    volts = ask_num("电池电压", 3.0, 24, 7.2, "V")
    per_shot = ask_num("单张耗电（CIPA 可反推）", 0.001, 100, 4, "mAh/张")
    video_w = ask_num("视频功耗", 0.1, 100, 6, "W")
    wh = cap_mah * volts / 1000.0
    shots = cap_mah * 0.9 / per_shot
    video_min = wh * 0.9 / video_w * 60
    text = head("56 · 电池续航估算")
    text += "\n" + kv([
        ("电池", f"{cap_mah:g} mAh / {volts:g} V = {wh:.1f} Wh"),
        ("单张耗电", f"{per_shot:g} mAh"),
        ("可拍张数", f"{shots:.0f} 张（按 90% 可用）"),
        ("视频时长", f"{video_min:.0f} 分钟（{video_w:g} W）"),
    ])
    text += "\n  提示：低温、连拍、机身防抖与屏幕亮度都会让实际张数低于估算。"
    finish(text)


# ======================= 60 · 天文 / 航拍 =======================
def m61():
    lens = ask_lens(24)
    pitch, px_w = ask_pitch(lens["w"], 6000)
    dec = ask_num("天体赤纬（0 = 天赤道最严重，60 = 高纬）", -80, 80, 0, "°")
    n_val = ask_num("光圈 F 值", 0.5, 128, 1.8, "F")
    t500 = 500.0 / lens["eqf"]
    t400 = 400.0 / lens["eqf"]
    t_npf = (35 * n_val + 30 * pitch) / lens["f"]
    cosd = math.cos(math.radians(dec))
    drag = lambda t: (0.004167 * t * cosd) / pixel_angle_deg(pitch, lens["f"])
    text = head("61 · 星野拖线：500 法则 / NPF")
    text += "\n" + kv([
        ("镜头", f"{lens['f']:g} mm（等效 {lens['eqf']:.0f} mm），F{n_val:g}"),
        ("像元间距", f"{pitch:.2f} um"),
        ("500 法则", f"{t500:.1f} s（拖线 {drag(t500):.1f} px）"),
        ("400 法则", f"{t400:.1f} s（拖线 {drag(t400):.1f} px）"),
        ("NPF 法则", f"{t_npf:.1f} s（拖线 {drag(t_npf):.1f} px）"),
        ("建议单张", f"{min(t_npf, t500):.1f} s 以内"),
    ])
    text += "\n\n  不同曝光下的拖线像素："
    rows = [[f"{t:g}s", f"{drag(t):.1f}"] for t in [5, 10, 15, 20, 30]]
    text += "\n" + table(["曝光", "拖线 px"], rows, ["right", "right"])
    text += "\n  提示：500 法则是老胶片经验，高像素机建议用 NPF，赤纬越高可拍越久。"
    finish(text)


def m62():
    lens = ask_lens(50)
    n_val = ask_num("光圈 F 值", 0.5, 128, 4, "F")
    t = ask_num("单张曝光", 0.1, 3600, 60, "s", parse=parse_shutter)
    frames = ask_int("叠加张数", 1, 5000, 50, "张")
    signal = ask_num("单张目标信号（电子/像素）", 0.01, 1e7, 200, "e-")
    read_noise = ask_num("读出噪声", 0.1, 100, 3, "e-")
    dark = ask_num("暗电流", 0, 100, 0.5, "e-/s")
    sky = ask_num("天空背景", 0, 10000, 5, "e-/s")
    ap = lens["f"] / n_val
    total_sig = signal * frames
    shot = signal * frames
    read_tot = read_noise ** 2 * frames
    dark_tot = (dark + sky) * t * frames
    noise = math.sqrt(shot + read_tot + dark_tot)
    snr = total_sig / noise if noise > 0 else INF
    text = head("62 · 深空信噪比与集光力")
    text += "\n" + kv([
        ("光学", f"{lens['f']:g} mm F{n_val:g}，有效口径 {ap:.1f} mm"),
        ("集光面积", f"{math.pi * (ap / 2) ** 2:.0f} mm²"),
        ("曝光", f"{frames} × {fmt_shutter(t)} = {frames * t / 60:.1f} min"),
        ("总信号", f"{total_sig:,.0f} e-"),
        ("总噪声", f"{noise:,.1f} e-"),
        ("SNR", f"{snr:.2f}"),
        ("等效单张 SNR", f"{(signal / math.sqrt(signal + read_noise ** 2 + (dark + sky) * t)):.2f}"),
    ])
    text += "\n  提示：叠加提升 SNR 约 √N；短曝光时读出噪声占主导，长曝则天空背景占主导。"
    finish(text)


def m63():
    lens = ask_lens(24)
    fh, fv, _fd, _ = fov_angles(lens["w"], lens["h"], lens["f"])
    n_val = ask_num("光圈 F 值", 0.5, 128, 2.8, "F")
    iso = ask_num("ISO", 6, 409600, 3200, "ISO")
    t = ask_num("单张快门", 0.1, 120, 15, "s", parse=parse_shutter)
    gap = ask_num("张间间隔", 0, 120, 1, "s")
    hours = ask_num("计划拍摄时长", 0.1, 24, 4, "h")
    count = int(hours * 3600 / (t + gap))
    text = head("63 · 流星雨拍摄")
    text += "\n" + kv([
        ("镜头", f"{lens['f']:g} mm（等效 {lens['eqf']:.0f} mm）"),
        ("单张视场", f"{fh:.1f}° × {fv:.1f}°"),
        ("参数", f"F{n_val:g}，ISO{iso:g}，{fmt_shutter(t)}"),
        ("拍摄时长", f"{hours:g} h"),
        ("预计张数", f"{count} 张"),
        ("占卡空间（20MB/张）", f"{count * 20 / 1024:.1f} GB"),
    ])
    text += "\n  提示：广角大光圈 + 高 ISO + 15s 左右最稳；关机身长曝降噪，间隔尽量小以免漏流星。"
    finish(text)


def m64():
    lens = ask_lens(200)
    pitch, px_w = ask_pitch(lens["w"], 6000)
    diam_arcmin = ask_num("月亮视直径", 25, 40, 31, "角分")
    phase = ask_num("月相照明比例", 0, 100, 100, "%")
    size_mm = lens["f"] * math.tan(math.radians(diam_arcmin / 60.0))
    px = size_mm / (pitch / 1000.0)
    px_h = lens["h"] * 1000.0 / pitch
    fill_w = px / px_w * 100
    fill_h = px / px_h * 100
    iso = 100
    text = head("64 · 月面成像与曝光")
    text += "\n" + kv([
        ("镜头", f"{lens['f']:g} mm（等效 {lens['eqf']:.0f} mm）"),
        ("月面直径", f"{size_mm:.2f} mm = {px:.0f} px"),
        ("占画面宽度", f"{fill_w:.1f}%"),
        ("占画面高度", f"{fill_h:.1f}%"),
        ("Looney 11 基准", f"F11，1/{iso}s，ISO{iso}"),
        ("月相", f"{phase:.0f}% 照明"),
        ("建议", "满月可再快 1 档避免过曝；弦月保持基准，背景会更黑"),
    ])
    f_fill = lens["w"] / math.tan(math.radians(diam_arcmin / 60.0)) * 0.9
    text += f"\n  若想让月亮占满画面宽度，约需 {f_fill:.0f} mm 物理焦距（等效 {f_fill * lens['crop']:.0f} mm）。"
    finish(text)


def m65():
    lens = ask_lens(135)
    pitch, _px = ask_pitch(lens["w"], 6000)
    drift = ask_num("彗星相对恒星漂移速度", 0.01, 600, 15, "角秒/秒")
    t_fixed = (pixel_angle_deg(pitch, lens["f"]) * 3600) / drift
    text = head("65 · 彗星拍摄：不拖尾上限")
    text += "\n" + kv([
        ("镜头", f"{lens['f']:g} mm（等效 {lens['eqf']:.0f} mm）"),
        ("单像素张角", f"{pixel_angle_deg(pitch, lens['f']) * 3600:.1f} 角秒"),
        ("漂移速度", f"{drift:g} 角秒/秒"),
        ("单张上限（1px）", f"{t_fixed:.2f} s"),
        ("单张上限（2px）", f"{t_fixed * 2:.2f} s"),
        ("建议", "要更长就上赤道仪并做彗星+恒星分别对齐叠加"),
    ])
    text += "\n  提示：彗星自身在动，500 法则不适用，按漂移速度算才是对的。"
    finish(text)


def m66():
    lens = ask_lens(14)
    n_val = ask_num("光圈 F 值", 0.5, 128, 1.8, "F")
    kp = ask_num("KP 指数", 0, 9, 5, "")
    t500 = 500.0 / lens["eqf"]
    if kp < 3:
        rec_t, rec_iso = 8, 3200
    elif kp < 5:
        rec_t, rec_iso = 5, 2000
    elif kp < 7:
        rec_t, rec_iso = 2.5, 1600
    else:
        rec_t, rec_iso = 1, 800
    text = head("66 · 极光拍摄参数")
    text += "\n" + kv([
        ("镜头", f"{lens['f']:g} mm（等效 {lens['eqf']:.0f} mm），F{n_val:g}"),
        ("KP 指数", f"{kp:g}"),
        ("推荐快门", f"{rec_t:g} s"),
        ("推荐 ISO", f"{rec_iso}"),
        ("星空不拖线上限", f"{t500:.1f} s"),
        ("权衡", "极光动得快，快门必须短；宁可高 ISO 也别糊"),
    ])
    text += "\n  提示：KP 越高极光越亮越快，强爆发时 1s 都能拍出结构；弱极光要 5~10s 换细节。"
    finish(text)


def m67():
    lens = ask_lens(400)
    n_val = ask_num("光圈 F 值", 0.5, 128, 8, "F")
    kind = ask_choice("拍什么", [("p", "日偏食（必须巴德膜）"),
                                 ("t", "日全食（全食阶段可摘膜）"),
                                 ("a", "日环食（不能摘膜）"),
                                 ("m", "月食（无需滤镜）")], "p")
    if kind == "p":
        iso, t, tip = 100, 1 / 1000, "太阳极亮，必须巴德膜 + 高速快门，切勿目视"
    elif kind == "t":
        iso, t, tip = 400, 1 / 15, "只有全食的 2~3 分钟可摘膜，生光前必须戴回"
    elif kind == "a":
        iso, t, tip = 100, 1 / 500, "环食依旧极亮，巴德膜全程不能摘"
    else:
        iso, t, tip = 800, 2, "月食亮度低，长焦 + 三脚架，按月亮正常曝光再放慢"
    text = head("67 · 日食 / 月食曝光基准")
    text += "\n" + kv([
        ("镜头", f"{lens['f']:g} mm（等效 {lens['eqf']:.0f} mm），F{n_val:g}"),
        ("类型", {"p": "日偏食", "t": "日全食", "a": "日环食", "m": "月食"}[kind]),
        ("基准曝光", f"F{n_val:g}，{fmt_shutter(t)}，ISO{iso}"),
        ("安全", tip),
    ])
    text += "\n  提示：除全食阶段外，镜头前必须加巴德膜（ND5 级）；用取景器直视会灼伤眼睛。"
    finish(text)


def m68():
    lens = ask_lens(300)
    pitch, px_w = ask_pitch(lens["w"], 6000)
    arcsec = ask_num("天体视直径", 0.1, 3600, 40, "角秒")
    size_mm = lens["f"] * math.tan(math.radians(arcsec / 3600.0))
    px = size_mm / (pitch / 1000.0)
    text = head("68 · 天体成像尺寸")
    text += "\n" + kv([
        ("镜头", f"{lens['f']:g} mm"),
        ("像元", f"{pitch:.2f} um"),
        ("视直径", f"{arcsec:g} 角秒"),
        ("成像直径", f"{size_mm * 1000:.1f} um"),
        ("占几个像素", f"{px:.1f} px"),
        ("像素比例", f"{pixel_angle_deg(pitch, lens['f']) * 3600:.2f} 角秒/px"),
    ])
    text += "\n  提示：行星想拍出细节，目标至少占 50 像素以上；不足就上增距镜或换更长焦距。"
    finish(text)


def m69():
    lens = ask_lens(300)
    pitch, _px = ask_pitch(lens["w"], 6000)
    err_arcmin = ask_num("极轴对准误差", 0.1, 120, 5, "角分")
    t = ask_num("单张曝光", 0.1, 3600, 300, "s", parse=parse_shutter)
    rate = err_arcmin * 15.0          # 角秒/分钟（经验近似）
    drift = rate * t / 60.0
    px = drift / (pixel_angle_deg(pitch, lens["f"]) * 3600)
    text = head("69 · 赤道仪追踪精度")
    text += "\n" + kv([
        ("镜头 / 像元", f"{lens['f']:g} mm，{pitch:.2f} um"),
        ("极轴误差", f"{err_arcmin:g} 角分"),
        ("漂移速率", f"约 {rate:.1f} 角秒/分钟（经验值）"),
        ("单张 {:.0f}s 漂移".format(t), f"{drift:.1f} 角秒 = {px:.1f} px"),
        ("建议", "超 2px 就缩短曝光或重新对极轴" if px > 2 else "在可接受范围"),
        ("可容忍时长", f"{2 * (pixel_angle_deg(pitch, lens['f']) * 3600) / rate * 60:.0f} s（2px 内）"),
    ])
    text += "\n  提示：极轴误差是长曝拖线的主因之一，其次才是周期误差与大气折射。"
    finish(text)


def m70():
    lens = ask_lens(24)
    px_w = ask_int("横向像素", 100, 200000, 5472, "px")
    px_h = ask_int("纵向像素", 100, 200000, 3648, "px")
    alt = ask_num("飞行高度", 1, 20000, 120, "m", parse=parse_dist_m)
    gsd_m = alt * lens["w"] / (lens["f"] * px_w)
    cover_w = gsd_m * px_w
    cover_h = gsd_m * px_h
    print("\n  可选：估算航线（不需要就直接用默认值）")
    area_w = ask_num("测区宽度", 10, 500000, 1000, "m", parse=parse_dist_m)
    area_h = ask_num("测区长度", 10, 500000, 1000, "m", parse=parse_dist_m)
    fwd = ask_num("航向重叠", 0.3, 0.95, 0.8, "")
    side = ask_num("旁向重叠", 0.1, 0.9, 0.7, "")
    line_gap = cover_w * (1 - side)
    other_gap = cover_h * (1 - fwd)
    lines = math.ceil(area_w / max(line_gap, 0.01)) + 1
    per_line = math.ceil(area_h / max(other_gap, 0.01)) + 1
    total = lines * per_line
    text = head("70 · 航测 GSD 与航线覆盖")
    text += "\n" + kv([
        ("相机", f"{lens['name']}，{lens['f']:g} mm，{px_w}×{px_h}"),
        ("航高", f"{alt:g} m"),
        ("GSD", f"{gsd_m * 100:.2f} cm/px（{gsd_m:.4f} m/px）"),
        ("单张覆盖", f"{cover_w:.1f} × {cover_h:.1f} m"),
        ("单张面积", f"{cover_w * cover_h / 10000:.2f} 公顷"),
        ("测区", f"{area_w / 1000:g} × {area_h / 1000:g} km（{area_w * area_h / 1e6:.2f} km²）"),
        ("航线间隔 / 拍照间隔", f"{line_gap:.1f} m / {other_gap:.1f} m"),
        ("航线数 / 每线张数", f"{lines} 条 / {per_line} 张"),
        ("总张数", f"{total} 张"),
        ("1 px 对应地面", f"{gsd_m * 100:.1f} cm"),
    ])
    text += "\n  提示：重叠率越高越安全（空三更稳），但张数与后期量暴涨；1:500 成图常要 80%/70%。"
    finish(text)


# ======================= 70 · 打印 / 色彩 / 画质 =======================
def m71():
    mode = ask_choice("算哪个？", [("a", "像素 + dpi → 打印尺寸"),
                                   ("b", "目标尺寸 + dpi → 需要多少像素"),
                                   ("c", "像素 + 尺寸 → 实际 dpi")], "a")
    if mode == "a":
        px_w = ask_int("像素宽", 10, 200000, 6000, "px")
        px_h = ask_int("像素高", 10, 200000, 4000, "px")
        dpi = ask_num("打印 dpi", 30, 1200, 300, "dpi")
        text = head("71 · 打印尺寸换算")
        text += "\n" + kv([
            ("像素", f"{px_w} × {px_h}"),
            ("dpi", f"{dpi:g}"),
            ("打印尺寸", f"{px_w / dpi * 2.54:.1f} × {px_h / dpi * 2.54:.1f} cm"),
            ("折合英寸", f"{px_w / dpi:.1f} × {px_h / dpi:.1f} in"),
            ("200 dpi 时", f"{px_w / 200 * 2.54:.1f} × {px_h / 200 * 2.54:.1f} cm"),
        ])
    elif mode == "b":
        w_cm = ask_num("成品宽度", 1, 500, 40, "cm", parse=parse_len_cm)
        h_cm = ask_num("成品高度", 1, 500, 30, "cm", parse=parse_len_cm)
        dpi = ask_num("打印 dpi", 30, 1200, 300, "dpi")
        need_w = int(w_cm / 2.54 * dpi)
        need_h = int(h_cm / 2.54 * dpi)
        text = head("71 · 需要多少像素")
        text += "\n" + kv([("成品", f"{w_cm:g} × {h_cm:g} cm"),
                           ("dpi", f"{dpi:g}"),
                           ("需要像素", f"{need_w} × {need_h} = {need_w * need_h / 1e6:.1f} MP")])
    else:
        px_w = ask_int("像素宽", 10, 200000, 6000, "px")
        w_cm = ask_num("成品宽度", 1, 500, 50, "cm", parse=parse_len_cm)
        dpi = px_w / (w_cm / 2.54)
        text = head("71 · 实际 dpi")
        text += "\n" + kv([("像素宽", f"{px_w}"),
                           ("成品宽", f"{w_cm:g} cm"),
                           ("实际 dpi", f"{dpi:.0f}"),
                           ("评价", "优秀" if dpi >= 300 else ("可接受" if dpi >= 150 else "偏软"))])
    text += "\n  提示：300dpi 是印刷标准，150dpi 大幅面喷绘也够；观看距离越远可用越低 dpi。"
    finish(text)


def m72():
    lens = ask_lens(50)
    view_cm = ask_num("观看距离", 10, 500, 50, "cm", parse=parse_len_cm)
    print_cm = ask_num("成品长边", 5, 500, 60, "cm", parse=parse_len_cm)
    visual_arcmin = ask_num("视力分辨角（正常 1~2 角分）", 0.5, 5, 1.5, "角分")
    view_mm = view_cm * 10.0
    coc_print = 2 * view_mm * math.tan(math.radians(visual_arcmin / 60.0) / 2)
    ratio = (print_cm * 10.0) / lens["w"]
    coc_sensor = coc_print / ratio
    text = head("72 · 观看距离决定的弥散圆")
    text += "\n" + kv([
        ("观看距离 / 成品长边", f"{view_cm:g} cm / {print_cm:g} cm"),
        ("肉眼可辨的最小点", f"{coc_print * 1000:.1f} um（纸上）"),
        ("折算到传感器", f"{coc_sensor * 1000:.1f} um"),
        ("对比常用 CoC", f"{coc_of(lens['w'], lens['h']) * 1000:.1f} um（对角线/1500）"),
        ("放大倍率", f"{ratio:.2f} ×（成品长边 / 传感器长边）"),
    ])
    text += "\n  提示：大幅面 + 远观看距离，景深要求可以放宽，不需要按 300dpi 死磕。"
    finish(text)


def m73():
    lens = ask_lens(35)
    overlap = ask_num("重叠率", 0.05, 0.9, 0.3, "")
    rows_count = ask_int("横拍几排", 1, 20, 1, "排")
    fh, _fv, _fd, _ = fov_angles(lens["w"], lens["h"], lens["f"])
    total_angle = ask_num("想覆盖的总水平角度", 1, 720, 180, "°")
    step = fh * (1 - overlap)
    n = max(1, math.ceil((total_angle - fh) / step) + 1)
    text = head("73 · 全景拼接张数")
    text += "\n" + kv([
        ("镜头水平视场", f"{fh:.1f}°（{lens['f']:g} mm）"),
        ("重叠率", f"{overlap * 100:.0f}%"),
        ("单张步进", f"{step:.1f}°"),
        ("目标覆盖", f"{total_angle:g}°"),
        ("所需张数", f"{n} 张 × {rows_count} 排 = {n * rows_count} 张"),
        ("等效覆盖", f"{fh + (n - 1) * step:.1f}°"),
    ])
    text += "\n  提示：重叠 30% 是安全值；云台每步转「视场 ×（1-重叠）」最省张数。"
    finish(text)


def m74():
    mode = ask_choice("要做什么？",
                      [("a", "色温 ↔ Mired"), ("b", "滤镜偏移后新色温"),
                       ("c", "从 A 色温调到 B 色温需要多少 Mired")], "a")
    if mode == "a":
        k = ask_num("色温", 1000, 20000, 5500, "K")
        text = head("74 · 色温与 Mired")
        text += "\n" + kv([("色温", f"{k:.0f} K"),
                           ("Mired", f"{mired(k):.1f}"),
                           ("常见对应", min(WB_TABLE, key=lambda x: abs(x[1] - k))[0])])
        text += "\n\n  常见色温参考："
        rows = [[name, k2, f"{mired(k2):.0f}"] for name, k2 in WB_TABLE]
        text += "\n" + table(["场景", "K", "Mired"], rows, ["left", "right", "right"])
    elif mode == "b":
        k = ask_num("原色温", 1000, 20000, 5500, "K")
        shift = ask_num("滤镜 Mired 偏移（负=偏蓝，正=偏黄）", -300, 300, 0, "Mired")
        new_k = kelvin(mired(k) + shift)
        text = head("74 · CC 滤镜偏移")
        text += "\n" + kv([("原色温", f"{k:.0f} K（{mired(k):.0f} Mired）"),
                           ("偏移", f"{shift:+g} Mired"),
                           ("新色温", f"{new_k:.0f} K（{mired(k) + shift:.0f} Mired）"),
                           ("校色方向", "更暖（黄）" if shift > 0 else ("更冷（蓝）" if shift < 0 else "无"))])
    else:
        ka = ask_num("当前色温", 1000, 20000, 5500, "K")
        kb = ask_num("目标色温", 1000, 20000, 4000, "K")
        text = head("74 · 色温调整量")
        text += "\n" + kv([("当前 / 目标", f"{ka:.0f} K / {kb:.0f} K"),
                           ("所需 Mired 偏移", f"{mired(kb) - mired(ka):+.1f}"),
                           ("方向", "加暖色滤镜" if kb < ka else "加冷色滤镜")])
    finish(text)


def m75():
    fwc = ask_num("满阱容量", 100, 1e7, 60000, "e-")
    read_noise = ask_num("读出噪声", 0.1, 100, 3, "e-")
    iso = ask_num("ISO", 6, 409600, 100, "ISO")
    base_iso = ask_num("基准 ISO", 6, 409600, 100, "ISO")
    effective_fwc = fwc * (base_iso / iso)
    dr = math.log2(effective_fwc / read_noise)
    text = head("75 · 动态范围估算")
    text += "\n" + kv([
        ("满阱 / 读出噪声", f"{fwc:,.0f} e- / {read_noise:g} e-"),
        ("当前 ISO", f"{iso:g}（基准 {base_iso:g}）"),
        ("有效满阱", f"{effective_fwc:,.0f} e-"),
        ("动态范围", f"{dr:.1f} 档"),
        ("可恢复高光", f"{dr - 3:.1f} 档（以中灰为基准粗估）"),
        ("每提 1 档 ISO", "动态范围约损失 1 档"),
    ])
    text += "\n  提示：这是传感器层面的理论上限，实际还受色彩滤镜、去噪与压缩影响。"
    finish(text)


# ======================= 参考表 =======================
def print_banner():
    print()
    print("=" * 68)
    print("   相机参数全能工具箱  v3.0        48 项计算 / 纯标准库 / 零依赖")
    print("=" * 68)


def print_reference():
    # 表 1 传感器
    print(head("参考表 1 · 常见传感器规格（编号与选传感器时一致）"))
    rows = []
    for i, (name, w, h, use) in enumerate(SENSORS, 1):
        d = math.hypot(w, h)
        rows.append([i, name, f"{w:g} × {h:g}", f"{d:.1f}", f"{FF_DIAG / d:.2f}",
                     f"{w * h / 100:.1f}", f"{d / COC_DIV * 1000:.0f}", use])
    print(table(["#", "规格", "宽×高 mm", "对角 mm", "裁切", "面积 cm²", "CoC um", "常见用途"],
                rows, ["right", "left", "left", "right", "right", "right", "right", "left"]))
    print("   裁切系数 = 43.27 / 对角线；CoC 按「对角线 / 1500」现代口径给出。")

    # 表 2 档位序列
    print(head("参考表 2 · 常用档位序列"))
    print("  光圈整档 : " + "  ".join(f"F{x:g}" for x in F_NUMS))
    print("  快门整档 : " + "  ".join(SHUTTER_STEPS))
    print("  ISO 整档 : " + "  ".join(str(x) for x in ISO_STEPS))
    print()
    print(table(["ND 编号", "减光档", "透过率"],
                [[n, f"{s:g}", f"{100 / 2 ** s:.2f}%"] for n, s in ND_TABLE],
                ["left", "right", "right"]))
    print("   每减 1 档 = 光线减半 = 快门翻倍。")

    # 表 3 焦距视角
    print(head("参考表 3 · 全画幅焦距 → 视角"))
    rows = []
    for f in [14, 16, 20, 24, 28, 35, 50, 85, 100, 135, 200, 300, 400]:
        fh, fv, fd, _ = fov_angles(FF_W, FF_H, f)
        rows.append([f"{f} mm", f"{fh:.1f}°", f"{fv:.1f}°", f"{fd:.1f}°",
                     FOCAL_USE.get(f, "—")])
    print(table(["焦距", "水平", "垂直", "对角", "典型用途"], rows,
                ["right", "right", "right", "right", "left"]))

    # 表 4 色温
    print(head("参考表 4 · 常见色温参考"))
    half = math.ceil(len(WB_TABLE) / 2)
    left = WB_TABLE[:half]
    right = WB_TABLE[half:]
    rows = []
    for i in range(half):
        l_name, l_k = left[i]
        if i < len(right):
            r_name, r_k = right[i]
            rows.append([l_name, l_k, r_name, r_k])
        else:
            rows.append([l_name, l_k, "", ""])
    print(table(["场景", "K", "场景", "K"], rows, ["left", "right", "left", "right"]))

    # 表 5 场景 EV
    print(head("参考表 5 · 场景亮度 EV100"))
    print(table(["EV100", "典型场景"],
                [[f"{ev}", name] for ev, name in EV_SCENE], ["right", "left"]))
    print("   晴天顺光 15；雪地 16；室内 9。EV 每 +1，进光量减半。")


def print_all_reference():
    print_reference()


# ======================= 菜单 =======================
CATS = [
    ("10 · 画幅 / 视场 / 采样", [
        (11, "FOV 正向：焦距 → 视场角"),
        (12, "FOV 反向：目标尺寸 → 所需焦距"),
        (13, "画面尺寸：距离 → 拍到多宽"),
        (14, "裁切系数 / 等效焦距换算"),
        (15, "传感器像素规格：像元间距 / 密度"),
        (16, "衍射极限 DLA 与艾里斑"),
        (17, "跨画幅等效：焦距 / 光圈 / ISO"),
        (18, "裁切后剩余像素与等效焦距"),
    ]),
    ("20 · 景深 / 对焦", [
        (21, "景深 & 超焦距"),
        (22, "景深表（多光圈对比）"),
        (23, "超焦距对焦法"),
        (24, "放大倍率与微距景深"),
        (25, "近摄接圈 / 增距镜"),
        (26, "焦点堆栈步进"),
        (27, "安全快门与手抖拖影"),
    ]),
    ("30 · 曝光", [
        (31, "EV 与曝光求解"),
        (32, "曝光等值组合表"),
        (33, "两组曝光差几档"),
        (34, "ND 滤镜与长曝时间"),
        (35, "长曝互易律补偿"),
        (36, "运动模糊 / 摇拍"),
        (37, "曝光补偿与包围曝光"),
    ]),
    ("40 · 闪光 / 照明", [
        (41, "GN 正算：需要多大灯"),
        (42, "GN 反算：能打多远 / 该用多大光圈"),
        (43, "闪光功率档位 & 高速同步"),
        (44, "平方反比与柔光光质"),
        (45, "闪光凝固能力"),
    ]),
    ("50 · 视频 / 数据", [
        (51, "快门角度 ↔ 快门速度"),
        (52, "存储卡录制时长"),
        (53, "升格 / 慢动作换算"),
        (54, "延时摄影"),
        (55, "文件体积估算"),
        (56, "电池续航估算"),
    ]),
    ("60 · 天文 / 航拍", [
        (61, "星野拖线：500 法则 / NPF"),
        (62, "深空信噪比与集光力"),
        (63, "流星雨拍摄"),
        (64, "月面成像与曝光"),
        (65, "彗星拍摄"),
        (66, "极光拍摄参数"),
        (67, "日食 / 月食曝光"),
        (68, "天体成像尺寸"),
        (69, "赤道仪追踪精度"),
        (70, "航测 GSD 与航线覆盖"),
    ]),
    ("70 · 打印 / 色彩 / 画质", [
        (71, "打印尺寸 & dpi 换算"),
        (72, "观看距离决定的弥散圆"),
        (73, "全景拼接张数"),
        (74, "色温 / Mired / CC 滤镜"),
        (75, "动态范围估算"),
    ]),
]

MODULES = {}
for _title, _items in CATS:
    for _n, _label in _items:
        _func = globals().get(f"m{_n}")
        if callable(_func):
            MODULES[_n] = _func


def show_menu(compact: bool = False):
    if compact:
        print()
        print("  " + "─" * 62)
        print("   输入编号继续算 · M 看完整菜单 · R 参考表 · L 记录 · Q 退出")
        print("  " + "─" * 62)
        return
    print()
    print("=" * 68)
    print("   主菜单          输入编号计算 · R 参考表 · L 记录 · Q 退出")
    print("=" * 68)
    for title, items in CATS:
        print(f"\n  ── {title} " + "─" * max(0, 46 - dw(title)))
        for n, label in items:
            print(f"   {n:>2}  {label}")
    print("\n   " + "-" * 60)
    print("   R 查看参考表      L 查看最近记录      Q 退出")


def show_log():
    if not os.path.exists(LOG_FILE):
        print("\n  [提示] 还没有任何记录。")
        return
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as fp:
            content = fp.read()
    except OSError as exc:
        print(f"\n  [提示] 读不到记录文件：{exc}")
        return
    blocks = content.split("=" * 64)
    tail = blocks[-3:] if len(blocks) > 3 else blocks
    print(f"\n  记录文件：{LOG_FILE}")
    print("  最近几条：")
    for block in tail:
        block = block.strip()
        if block:
            print("  " + block.replace("\n", "\n  ")[:900])
            print("  " + "-" * 40)


def pause():
    try:
        input("\n  按回车返回主菜单…")
    except (EOFError, KeyboardInterrupt):
        pass


# ======================= 自检 =======================
def selftest():
    fails = []

    def chk(name, got, want, tol=1e-6):
        good = abs(got - want) <= tol * max(1.0, abs(want))
        fails.append(name) if not good else None
        print(f"  [{'PASS' if good else 'FAIL'}] {name}: {got:.6g}  (期望 {want:.6g})")

    print("\n自检：核心公式")

    fh, fv, fd, diag = fov_angles(36, 24, 50)
    chk("36x24 f50 水平视场", fh, 39.5978, 2e-3)
    chk("36x24 f50 垂直视场", fv, 26.9915, 2e-3)
    chk("36x24 f50 对角视场", fd, 46.7930, 2e-3)
    chk("全画幅裁切系数", crop_factor(36, 24), 1.0, 1e-12)
    chk("APS-C 佳能裁切", crop_factor(22.3, 14.9), 1.6135, 1e-3)

    chk("36mm/6000px 像元", pixel_pitch_um(36, 6000), 6.0)
    chk("F8 艾里斑(um)", airy_um(8), 10.736)
    chk("F8 超焦距(mm)", hyperfocal_mm(50, 8, 0.03), 10466.667, 1e-3)

    near, far, hper = dof_range(50, 8, 3000, 0.03)
    chk("3m 对焦近界(mm)", near, 2337.56, 1e-3)
    chk("3m 对焦远界(mm)", far, 4186.05, 1e-3)

    chk("F8 1/125 ISO100 EV", ev100(8, 1 / 125, 100), 12.9658, 1e-3)
    chk("ND10 档 1/125→s", (1 / 125) * 2 ** 10, 8.192)
    chk("180度 25fps 快门", 180 / (360 * 25), 0.02)
    chk("NPF 24mm F2.8 p5.9", (35 * 2.8 + 30 * 5.9) / 24, 11.4583, 1e-3)
    chk("5500K Mired", mired(5500), 181.818, 1e-3)
    chk("反推焦距 36mm/10m/2m", 36 * 10 / 2, 180.0)
    chk("GSD 13.2mm/8.8mm/100m/5472px", 100 * 13.2 / (8.8 * 5472), 0.027414, 1e-3)

    # 输入解析
    chk("parse 1/125", parse_shutter("1/125"), 0.008)
    chk("parse 8ms", parse_shutter("8ms"), 0.008)
    chk("parse 2s", parse_shutter("2s"), 2.0)
    chk("parse 36mm", parse_len_mm("36mm"), 36.0)
    chk("parse 3.6cm", parse_len_mm("3.6cm"), 36.0)
    chk("parse 500cm→m", parse_dist_m("500cm"), 5.0)
    chk("parse 全角 1／125", parse_shutter("１／１２５"), 0.008)
    chk("parse 千分位 12,000", parse_dist_m("12,000"), 12000.0)

    print()
    if fails:
        print(f"  结果：{len(fails)} 项失败 → {', '.join(fails)}")
        return 1
    print("  结果：全部通过")
    return 0


# ======================= 主入口 =======================
def main():
    if "--selftest" in sys.argv:
        return selftest()

    print_banner()
    if "--no-ref" not in sys.argv:
        print_reference()

    first_menu = True
    while True:
        show_menu(compact=not first_menu)
        first_menu = False
        try:
            raw = input("  请输入功能编号（R / L / Q）：")
        except (EOFError, KeyboardInterrupt):
            print("\n  已退出。")
            break
        cmd = norm(raw).lower()
        if not cmd:
            continue
        if cmd in ("q", "quit", "exit", "0", "退出"):
            print(f"\n  已退出。计算记录保存在：{LOG_FILE}")
            break
        if cmd in ("m", "menu", "菜单", "h", "help"):
            show_menu()
            continue
        if cmd in ("r", "ref", "参考"):
            print_reference()
            pause()
            continue
        if cmd in ("l", "log", "记录"):
            show_log()
            pause()
            continue
        if not cmd.isdigit():
            print("  [提示] 请输入菜单中的编号，或 R / L / Q。")
            continue
        func = MODULES.get(int(cmd))
        if func is None:
            print("  [提示] 没有这个编号，请对照菜单。")
            continue
        try:
            func()
        except UserCancel:
            print("\n  已放弃本次计算（输入 q 或按了 Ctrl+C）。")
        except Exception as exc:                       # 兜底，避免整程序崩溃
            print(f"\n  [错误] 本次计算中断：{type(exc).__name__}: {exc}")
            print("  [提示] 这属于边界情况，可换个输入重试，或把这行信息反馈给我。")
        pause()


if __name__ == "__main__":
    sys.exit(main() or 0)
