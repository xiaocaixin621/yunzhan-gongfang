#!/usr/bin/env python3
"""
马拉多纳 · Life is Life
扫描式写生：横条纹 + 纵条纹逐步显现原图像素（最终高清清晰）。

⚠️  必须在项目虚拟环境中运行！

    cd /Users/mac/penguin_drawing && source .venv/bin/activate
    python Maradona/draw_maradona.py

配乐默认 life_is_life.mp3，与绘画墙钟同步（总时长 ≤300s）。
"""

from __future__ import annotations

import argparse
import atexit
import math
import os
import random
import signal
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# 路径 & 虚拟环境
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
VENV_DIR = PROJECT_ROOT / ".venv"
SRC_DEFAULT = HERE / "Maradona.jpg"
OUT_FINAL = HERE / "maradona_painted.png"
OUT_MP4 = HERE / "maradona.mp4"
OUT_FRAMES_DIR = HERE / "frames"
CALLIGRAPHY_FONT = HERE / "fonts" / "MaShanZheng-Regular.ttf"
MUSIC_DEFAULT = HERE / "life_is_life.mp3"
MUSIC_DESKTOP = Path.home() / "Desktop" / "life is life.mp3"
MUSIC_PID_FILE = HERE / ".life_is_life_afplay.pid"

BOARD = (252, 250, 246)
CINNABAR = (168, 28, 32)
GOLD = (196, 158, 72)
UI_BG = (13, 11, 10)

# 整场呈现时长（秒）— 观众注意力有限，默认 240s
PRESENTATION_MAX_S = 240.0
PRESENTATION_DEFAULT_S = 240.0


def _running_in_project_venv() -> bool:
    prefix = Path(sys.prefix).resolve()
    base = Path(getattr(sys, "base_prefix", sys.prefix)).resolve()
    venv = VENV_DIR.resolve()
    in_any_venv = prefix != base or bool(os.environ.get("VIRTUAL_ENV"))
    try:
        exe = Path(sys.executable).resolve()
        in_project = venv in exe.parents or prefix == venv or prefix.is_relative_to(venv)
    except Exception:
        in_project = str(venv) in str(Path(sys.executable).resolve())
    env = os.environ.get("VIRTUAL_ENV", "")
    env_ok = bool(env) and Path(env).resolve() == venv
    return in_any_venv and (in_project or env_ok)


def require_project_venv() -> None:
    if _running_in_project_venv():
        return
    print(
        f"""
❌ 拒绝在全局 Python 中运行。

    cd {PROJECT_ROOT}
    source .venv/bin/activate
    python Maradona/draw_maradona.py
""".strip(),
        file=sys.stderr,
    )
    raise SystemExit(1)


require_project_venv()

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageTk  # noqa: E402

# Op: 扫描/上彩操作
# ("h", y0, y1)  横条：粘贴原图 [0:w, y0:y1]
# ("v", x0, x1)  纵条：粘贴原图 [x0:x1, 0:h]
# ("wash", x, y, d, op)  早期淡铺色（可选）
# ("seal",)  整图锁定原图
Op = tuple


# ---------------------------------------------------------------------------
# 配乐
# ---------------------------------------------------------------------------


def resolve_music_path(explicit: Path | None = None) -> Path | None:
    for p in (explicit, MUSIC_DEFAULT, MUSIC_DESKTOP):
        if p is not None and p.is_file():
            return p.resolve()
    return None


def probe_audio_duration(path: Path) -> float | None:
    try:
        r = subprocess.run(
            ["afinfo", str(path)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                if "estimated duration" in line.lower():
                    for tok in line.replace(":", " ").split():
                        try:
                            v = float(tok)
                            if 5.0 < v < 36000:
                                return v
                        except ValueError:
                            continue
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        r = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if r.returncode == 0 and r.stdout.strip():
            return float(r.stdout.strip())
    except (OSError, subprocess.TimeoutExpired, ValueError):
        pass
    return None


def compute_presentation_duration(
    music_dur: float | None,
    explicit: float | None,
) -> tuple[float, float]:
    """
    返回 (painting_duration, music_rate)。
    默认 240s 内完成；music_rate 使配乐与墙钟同步结束。
    rate > 1 略加快歌曲，rate < 1 略放慢。
    """
    if explicit is not None:
        dur = max(30.0, min(PRESENTATION_MAX_S, explicit))
    else:
        dur = PRESENTATION_DEFAULT_S

    if music_dur and music_dur > 0:
        rate = max(0.5, min(2.0, music_dur / dur))
        return dur, rate
    return dur, 1.0


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def kill_orphan_music(verbose: bool = True) -> int:
    """
    杀掉上次崩溃残留的配乐进程（afplay / 本项目 mp3）。
    返回杀掉的进程数。
    """
    killed = 0
    # 1) pid 文件
    if MUSIC_PID_FILE.is_file():
        try:
            pid = int(MUSIC_PID_FILE.read_text().strip())
            if _pid_alive(pid):
                try:
                    os.kill(pid, signal.SIGTERM)
                    killed += 1
                    if verbose:
                        print(f"  ♪ 已停止残留配乐 pid={pid}")
                except OSError:
                    pass
        except ValueError:
            pass
        try:
            MUSIC_PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass

    # 2) 扫描 afplay 命令行中含本项目 mp3 名的进程
    markers = ("life_is_life.mp3", "life is life.mp3", str(MUSIC_DEFAULT))
    try:
        out = subprocess.check_output(["ps", "-ax", "-o", "pid=,command="], text=True)
    except (OSError, subprocess.CalledProcessError):
        out = ""
    for line in out.splitlines():
        line = line.strip()
        if not line or "afplay" not in line:
            continue
        if not any(m in line for m in markers):
            continue
        try:
            pid = int(line.split(None, 1)[0])
        except ValueError:
            continue
        if pid == os.getpid():
            continue
        try:
            os.kill(pid, signal.SIGTERM)
            killed += 1
            if verbose:
                print(f"  ♪ 已停止残留配乐 pid={pid}")
        except OSError:
            pass
    return killed


class BackgroundMusic:
    """播放配乐；进程退出/崩溃清理时尽量带走 afplay。"""

    _active: "BackgroundMusic | None" = None

    def __init__(self, path: Path, rate: float = 1.0):
        self.path = path
        self.rate = max(0.5, min(2.0, rate))
        self.proc: subprocess.Popen | None = None
        self.paused = False

    @property
    def playing(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def _write_pid(self, pid: int) -> None:
        try:
            MUSIC_PID_FILE.write_text(str(pid))
        except OSError:
            pass

    def _clear_pid(self) -> None:
        try:
            MUSIC_PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass

    def start(self) -> bool:
        self.stop()
        kill_orphan_music(verbose=False)
        if not self.path.is_file():
            return False
        if sys.platform == "darwin":
            cmd = ["afplay", "-r", f"{self.rate:.5f}", "-q", "1", str(self.path)]
        else:
            tempo = max(0.5, min(2.0, self.rate))
            cmd = [
                "ffplay",
                "-nodisp",
                "-autoexit",
                "-loglevel",
                "quiet",
                "-af",
                f"atempo={tempo:.5f}",
                str(self.path),
            ]
        try:
            # 不 start_new_session：崩溃时尽量不脱离父进程
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.paused = False
            self._write_pid(self.proc.pid)
            BackgroundMusic._active = self
            return True
        except OSError as e:
            print(f"  ⚠ 无法播放配乐: {e}", file=sys.stderr)
            self.proc = None
            return False

    def pause(self) -> None:
        if not self.playing or self.paused:
            return
        try:
            os.kill(self.proc.pid, signal.SIGSTOP)
            self.paused = True
        except (OSError, ProcessLookupError):
            pass

    def resume(self) -> None:
        if not self.proc or not self.paused:
            return
        try:
            os.kill(self.proc.pid, signal.SIGCONT)
            self.paused = False
        except (OSError, ProcessLookupError):
            pass

    def stop(self) -> None:
        if self.proc is not None:
            try:
                if self.paused:
                    try:
                        os.kill(self.proc.pid, signal.SIGCONT)
                    except (OSError, ProcessLookupError):
                        pass
                self.proc.send_signal(signal.SIGTERM)
                try:
                    self.proc.wait(timeout=1.5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=1.0)
            except (OSError, ProcessLookupError):
                pass
            self.proc = None
            self.paused = False
        self._clear_pid()
        if BackgroundMusic._active is self:
            BackgroundMusic._active = None


def _atexit_stop_music() -> None:
    m = BackgroundMusic._active
    if m is not None:
        m.stop()
    kill_orphan_music(verbose=False)


atexit.register(_atexit_stop_music)


# ---------------------------------------------------------------------------
# 图像 / 扫描计划
# ---------------------------------------------------------------------------


def load_source(path: Path, scale: float) -> Image.Image:
    img = Image.open(path).convert("RGB")
    if abs(scale - 1.0) > 1e-3:
        w, h = img.size
        img = img.resize(
            (max(1, int(w * scale)), max(1, int(h * scale))),
            Image.Resampling.LANCZOS,
        )
    # 轻锐化，最终扫描贴原图时更利落
    return img.filter(ImageFilter.UnsharpMask(radius=0.7, percent=45, threshold=2))


def make_scan_plan(w: int, h: int, rng: random.Random) -> list[Op]:
    """
    渐进扫描显现（非遮罩点破泡沫）：
      1) 极淡大块洗色（虚影，不成形）
      2) 隔行横扫（由疏到密）—— 像 CRT/打印机扫描
      3) 隔列纵扫（交叉补全）
      4) 全像素横扫 + 全像素纵扫锁清
      5) seal 整图 = 原图，脸部绝对清晰
    """
    ops: list[Op] = []
    short = min(w, h)

    # —— 1. 淡洗：少而虚，只铺气势 ——
    for _ in range(120):
        x = rng.randint(0, w - 1)
        y = rng.randint(0, h - 1)
        d = rng.randint(short // 10, short // 5)
        ops.append(("wash", x, y, d, 0.18))

    # —— 2. 横向隔行扫描：step 从大到小 ——
    for step in (32, 16, 8, 4, 2):
        rows = list(range(0, h, step))
        # 略作波纹顺序，仍大体自上而下
        # 分块：先偶数组再奇数组，增强「扫描感」
        even = rows[0::2]
        odd = rows[1::2]
        for y in even + odd:
            y1 = min(h, y + max(1, step // 2))
            ops.append(("h", y, y1))

    # —— 3. 纵向隔列扫描 ——
    for step in (32, 16, 8, 4, 2):
        cols = list(range(0, w, step))
        even = cols[0::2]
        odd = cols[1::2]
        for x in even + odd:
            x1 = min(w, x + max(1, step // 2))
            ops.append(("v", x, x1))

    # —— 4. 全分辨率横扫（逐行，一次成型清晰）——
    band = 2  # 每次 2 行，动画更顺
    for y in range(0, h, band):
        ops.append(("h", y, min(h, y + band)))

    # —— 5. 全分辨率纵扫（交叉锁边，五官更利）——
    band = 2
    for x in range(0, w, band):
        ops.append(("v", x, min(w, x + band)))

    # —— 6. 整图封印：像素级 = 原图 ——
    ops.append(("seal",))
    return ops


# ---------------------------------------------------------------------------
# 画师：扫描上彩
# ---------------------------------------------------------------------------


class Painter:
    def __init__(self, source: Image.Image, ops: list[Op]):
        self.source = source
        self.ops = ops
        self.w, self.h = source.size
        self.src_px = source.load()
        self.canvas = Image.new("RGB", (self.w, self.h), BOARD)
        # 洗色用强模糊参考
        self.blur = source.resize(
            (max(1, self.w // 24), max(1, self.h // 24)), Image.Resampling.BILINEAR
        ).resize((self.w, self.h), Image.Resampling.BILINEAR)
        self.blur_px = self.blur.load()
        self._wash_brush_cache: dict[int, Image.Image] = {}
        self.i = 0

    def _wash_brush(self, d: int) -> Image.Image:
        d = max(8, d | 1)
        if d not in self._wash_brush_cache:
            br = Image.new("L", (d, d), 0)
            dr = ImageDraw.Draw(br)
            c = d // 2
            for r in range(c, 0, -1):
                t = r / c
                val = int(255 * (1.0 - t) ** 1.6)
                dr.ellipse([c - r, c - r, c + r, c + r], fill=val)
            self._wash_brush_cache[d] = br
        return self._wash_brush_cache[d]

    def apply_one(self, op: Op) -> None:
        kind = op[0]
        if kind == "h":
            _, y0, y1 = op
            y0 = max(0, min(self.h, y0))
            y1 = max(y0, min(self.h, y1))
            if y1 <= y0:
                return
            strip = self.source.crop((0, y0, self.w, y1))
            self.canvas.paste(strip, (0, y0))
        elif kind == "v":
            _, x0, x1 = op
            x0 = max(0, min(self.w, x0))
            x1 = max(x0, min(self.w, x1))
            if x1 <= x0:
                return
            strip = self.source.crop((x0, 0, x1, self.h))
            self.canvas.paste(strip, (x0, 0))
        elif kind == "wash":
            _, x, y, d, opacity = op
            x = max(0, min(self.w - 1, int(x)))
            y = max(0, min(self.h - 1, int(y)))
            br = self._wash_brush(int(d))
            # 降低 alpha
            mask = br.point(lambda v, o=opacity: int(v * o))
            c = self.blur_px[x, y]
            color = (int(c[0]), int(c[1]), int(c[2]))
            gray = int(0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2])
            color = (
                int(color[0] * 0.5 + gray * 0.5),
                int(color[1] * 0.5 + gray * 0.5),
                int(color[2] * 0.5 + gray * 0.5),
            )
            patch = Image.new("RGB", br.size, color)
            self.canvas.paste(patch, (x - br.size[0] // 2, y - br.size[1] // 2), mask)
        elif kind == "seal":
            self.canvas.paste(self.source)

    def apply_range(self, i0: int, i1: int) -> None:
        for j in range(i0, i1):
            self.apply_one(self.ops[j])
        self.i = i1

    def snapshot(self) -> Image.Image:
        return self.canvas.copy()

    def final_image(self) -> Image.Image:
        # 扫描终点 = 原图；再极轻锐化
        img = self.source.copy()
        img = img.filter(ImageFilter.UnsharpMask(radius=1.0, percent=70, threshold=2))
        return img


# ---------------------------------------------------------------------------
# 书法题匾（可按 alpha 渐进）
# ---------------------------------------------------------------------------


def load_calligraphy_font(size: int) -> ImageFont.ImageFont:
    if CALLIGRAPHY_FONT.is_file():
        try:
            return ImageFont.truetype(str(CALLIGRAPHY_FONT), size=size)
        except OSError:
            pass
    for path in (
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ):
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_calligraphy_banner(
    text: str = "致敬马拉多纳",
    width: int = 900,
    height: int = 72,
    alpha: float = 1.0,
) -> Image.Image:
    """alpha 0~1：渐进显现题匾（置顶，偏矮以放大画布）。"""
    alpha = max(0.0, min(1.0, alpha))
    bg = UI_BG
    base = Image.new("RGB", (width, height), bg)
    if alpha < 0.02:
        return base

    layer = Image.new("RGBA", (width, height), (*bg, 0))
    draw = ImageDraw.Draw(layer)
    size = max(32, min(int(height * 0.78), int(width * 0.085)))
    font = load_calligraphy_font(size)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    while tw > width * 0.92 and size > 36:
        size = int(size * 0.92)
        font = load_calligraphy_font(size)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (width - tw) // 2 - bbox[0]
    y = (height - th) // 2 - bbox[1] - 2

    a = int(255 * alpha)
    for ox, oy in (
        (-3, 0),
        (3, 0),
        (0, -3),
        (0, 3),
        (-2, -2),
        (2, 2),
        (-2, 2),
        (2, -2),
    ):
        draw.text((x + ox, y + oy), text, font=font, fill=(12, 6, 6, a))
    for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        draw.text((x + ox, y + oy), text, font=font, fill=(90, 16, 18, a))
    draw.text((x, y), text, font=font, fill=(*CINNABAR, a))
    draw.text((x - 1, y - 1), text, font=font, fill=(210, 48, 42, a))

    ly = height - 14
    ga = int(220 * alpha)
    draw.line(
        [(int(width * 0.18), ly), (int(width * 0.82), ly)],
        fill=(*GOLD, ga),
        width=2,
    )

    out = Image.new("RGB", (width, height), bg)
    out.paste(layer, (0, 0), layer)
    return out


def render_subtitle(width: int, alpha: float = 1.0) -> Image.Image:
    """副标渐进。"""
    alpha = max(0.0, min(1.0, alpha))
    h = 28
    img = Image.new("RGB", (width, h), UI_BG)
    if alpha < 0.02:
        return img
    draw = ImageDraw.Draw(img)
    text = "不 屈  ·  真 男 人  ·  LIFE IS LIFE"
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 18)
    except OSError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (width - tw) // 2 - bbox[0]
    y = (h - th) // 2 - bbox[1]
    a = int(255 * alpha)
    # 画在 RGBA 再贴
    layer = Image.new("RGBA", (width, h), (*UI_BG, 0))
    d2 = ImageDraw.Draw(layer)
    d2.text((x, y), text, font=font, fill=(*GOLD, a))
    img.paste(layer, (0, 0), layer)
    return img


# ---------------------------------------------------------------------------
# 输出 / Headless
# ---------------------------------------------------------------------------


def save_hd_png(img: Image.Image, path: Path) -> None:
    img.save(path, "PNG", compress_level=3, optimize=False)


def run_headless(painter: Painter, duration_s: float, save_frames: bool) -> Image.Image:
    """无界面：尽快画完（不按墙钟）。"""
    total = len(painter.ops)
    batch = max(1, total // 200)
    t0 = time.time()
    frame_idx = 0
    if save_frames:
        OUT_FRAMES_DIR.mkdir(parents=True, exist_ok=True)
        for old in OUT_FRAMES_DIR.glob("frame_*.png"):
            old.unlink()
        save_hd_png(painter.snapshot(), OUT_FRAMES_DIR / f"frame_{frame_idx:04d}.png")
        frame_idx += 1
    step = 0
    while painter.i < total:
        painter.apply_range(painter.i, min(total, painter.i + batch))
        step += 1
        if save_frames and step % 5 == 0:
            save_hd_png(painter.snapshot(), OUT_FRAMES_DIR / f"frame_{frame_idx:04d}.png")
            frame_idx += 1
        if painter.i % max(1, total // 20) < batch or painter.i >= total:
            print(
                f"\r  扫描进度 {painter.i/total*100:5.1f}%  {time.time()-t0:.1f}s",
                end="",
                flush=True,
            )
    print()
    return painter.final_image()


# ---------------------------------------------------------------------------
# GUI：墙钟同步 + 标题渐进 + 配乐
# ---------------------------------------------------------------------------


def run_gui(
    painter: Painter,
    duration_s: float,
    save_frames: bool,
    music: BackgroundMusic | None = None,
) -> None:
    import tkinter as tk
    from tkinter import ttk

    w, h = painter.w, painter.h
    # 题匾偏矮，把纵向空间尽量留给大画布
    BANNER_H = 72
    SUB_H = 28
    CHROME_H = 56  # 底部进度文字 + 进度条

    if save_frames:
        OUT_FRAMES_DIR.mkdir(parents=True, exist_ok=True)
        for old in OUT_FRAMES_DIR.glob("frame_*.png"):
            old.unlink()

    # 只创建一次 Tk（macOS 上 destroy 后再 new Tk 极易 bus error）
    root = tk.Tk()
    root.title("致敬马拉多纳 · Life is Life")
    root.configure(bg="#0d0b0a")
    root.update_idletasks()

    scr_h = max(600, int(root.winfo_screenheight() or 900))
    scr_w = max(800, int(root.winfo_screenwidth() or 1400))
    # 大画布：尽量 1:1 原图像素显示；屏小则按屏缩放（不再卡在 900 宽）
    max_canvas_h = max(480, scr_h - BANNER_H - SUB_H - CHROME_H - 36)
    max_canvas_w = max(480, scr_w - 32)
    scale_show = min(max_canvas_w / w, max_canvas_h / h, 1.0)
    sw, sh = max(1, int(w * scale_show)), max(1, int(h * scale_show))
    banner_w = max(sw, 720)

    # —— 布局：标题置顶 → 大画布 → 进度在画布底部 ——
    banner_label = tk.Label(root, bg="#0d0b0a", bd=0)
    banner_label.pack(pady=(6, 0))
    sub_label = tk.Label(root, bg="#0d0b0a", bd=0)
    sub_label.pack(pady=(0, 2))

    canvas_label = tk.Label(
        root,
        bg="#111111",
        bd=0,
        highlightthickness=2,
        highlightbackground="#5c1218",
    )
    canvas_label.pack(padx=8, pady=(4, 2))

    status = tk.Label(
        root,
        text="进度  0%    已用 0s / 剩余 --s",
        font=("Helvetica", 13, "bold"),
        fg="#d4b896",
        bg="#0d0b0a",
    )
    status.pack(pady=(4, 2))
    progress = ttk.Progressbar(root, length=sw, mode="determinate", maximum=100)
    progress.pack(pady=(0, 10))

    state = {
        "paused": False,
        "done": False,
        "t0": 0.0,
        "pause_acc": 0.0,
        "pause_at": 0.0,
        "photo": None,
        "banner_photo": None,
        "sub_photo": None,
        "frame_idx": 0,
        "music_started": False,
        "title_alpha": -1.0,
        "sub_alpha": -1.0,
    }
    total = len(painter.ops)

    def fmt_time(sec: float) -> str:
        sec = max(0, int(sec))
        m, s = divmod(sec, 60)
        return f"{m}:{s:02d}" if m else f"{s}s"

    def progress_text(pct: float, elapsed: float, remain: float, note: str = "") -> str:
        return (
            f"进度  {pct:4.0f}%    "
            f"已用 {fmt_time(elapsed)} / 剩余 {fmt_time(remain)}"
            f"{note}"
        )

    def effective_elapsed() -> float:
        if state["t0"] <= 0:
            return 0.0
        now = time.time()
        if state["paused"]:
            return max(0.0, state["pause_at"] - state["t0"] - state["pause_acc"])
        return max(0.0, now - state["t0"] - state["pause_acc"])

    def to_photo(img: Image.Image) -> ImageTk.PhotoImage:
        """统一 RGB + 拷贝，避免 Tk/ImageTk 在 macOS 上 bus error。"""
        if img.mode != "RGB":
            img = img.convert("RGB")
        else:
            img = img.copy()
        return ImageTk.PhotoImage(img, master=root)

    def refresh_canvas(img: Image.Image) -> None:
        show = img if (sw, sh) == (w, h) else img.resize((sw, sh), Image.Resampling.BILINEAR)
        state["photo"] = to_photo(show)
        canvas_label.configure(image=state["photo"])

    def set_title_alpha(ta: float, sa: float) -> None:
        tq = round(ta, 2)
        sq = round(sa, 2)
        try:
            if abs(tq - state["title_alpha"]) >= 0.02 or state["title_alpha"] < 0:
                state["title_alpha"] = tq
                bimg = render_calligraphy_banner(
                    "致敬马拉多纳", width=banner_w, height=BANNER_H, alpha=tq
                )
                state["banner_photo"] = to_photo(bimg)
                banner_label.configure(image=state["banner_photo"])
            if abs(sq - state["sub_alpha"]) >= 0.02 or state["sub_alpha"] < 0:
                state["sub_alpha"] = sq
                simg = render_subtitle(banner_w, alpha=sq)
                state["sub_photo"] = to_photo(simg)
                sub_label.configure(image=state["sub_photo"])
        except Exception as e:
            # 标题渲染失败不拖垮主程序
            print(f"  ⚠ 标题刷新失败: {e}", file=sys.stderr)

    # 初始画面（延迟一帧，等 Tk 完全就绪）
    def _init_ui() -> None:
        set_title_alpha(0.0, 0.0)
        refresh_canvas(painter.snapshot())

    root.after(50, _init_ui)

    def stop_music() -> None:
        if music is not None:
            music.stop()

    def finish() -> None:
        if state["done"]:
            return
        state["done"] = True
        # 确保扫完
        if painter.i < total:
            painter.apply_range(painter.i, total)
        final = painter.final_image()
        refresh_canvas(final)
        set_title_alpha(1.0, 1.0)
        save_hd_png(final, OUT_FINAL)
        if save_frames:
            save_hd_png(final, OUT_FRAMES_DIR / f"frame_{state['frame_idx']:04d}.png")
        elapsed = effective_elapsed()
        status.configure(
            text=progress_text(100, elapsed, 0) + "    完成 · Esc 关闭"
        )
        progress["value"] = 100
        print(f"\n✓ 致敬完成 → {OUT_FINAL}")
        print(f"  分辨率 {w}×{h}  操作 {total}  墙钟 {elapsed:.1f}s / 目标 {duration_s:.1f}s")
        root.after(1500, stop_music)

    def begin() -> None:
        if music is not None and not state["music_started"]:
            ok = music.start()
            state["music_started"] = ok
            print(
                f"  ♪ 配乐开始 rate={music.rate:.3f}  目标同步 {duration_s:.1f}s"
                if ok
                else "  ⚠ 配乐未能启动"
            )
        state["t0"] = time.time()
        tick()

    def tick() -> None:
        """墙钟驱动：按 elapsed/duration 推进扫描，保证与配乐同步结束。"""
        if state["done"]:
            return
        if state["paused"]:
            root.after(50, tick)
            return

        elapsed = effective_elapsed()
        # 进度 0~1，留 1.5% 给 seal
        t = min(1.0, elapsed / max(0.1, duration_s))
        target_i = int(total * t)
        if target_i > painter.i:
            # 若掉帧则一次追上（保证不拖过曲终）
            painter.apply_range(painter.i, min(total, target_i))
            refresh_canvas(painter.snapshot())

        pct = painter.i / total * 100
        progress["value"] = min(100, pct)

        # 标题渐进：主标 5%~28%，副标 18%~42%
        title_a = 0.0 if t < 0.05 else min(1.0, (t - 0.05) / 0.23)
        sub_a = 0.0 if t < 0.18 else min(1.0, (t - 0.18) / 0.24)
        set_title_alpha(title_a, sub_a)

        remain = max(0.0, duration_s - elapsed)
        note = "  ♪" if music and music.playing and not music.paused else ""
        status.configure(text=progress_text(pct, elapsed, remain, note))

        if save_frames and painter.i > 0 and painter.i % max(1, total // 80) == 0:
            save_hd_png(
                painter.snapshot(),
                OUT_FRAMES_DIR / f"frame_{state['frame_idx']:04d}.png",
            )
            state["frame_idx"] += 1

        if painter.i >= total and elapsed >= duration_s * 0.98:
            finish()
            return
        if elapsed >= duration_s:
            # 时间到：瞬间扫完剩余并收束
            if painter.i < total:
                painter.apply_range(painter.i, total)
                refresh_canvas(painter.snapshot())
            finish()
            return

        # ~30fps 调度；实际推进量由墙钟决定
        root.after(33, tick)

    def on_key(event) -> None:
        if event.keysym in ("space", "p"):
            if not state["paused"]:
                state["paused"] = True
                state["pause_at"] = time.time()
                if music:
                    music.pause()
                el = effective_elapsed()
                status.configure(
                    text=progress_text(
                        painter.i / max(1, total) * 100,
                        el,
                        max(0.0, duration_s - el),
                    )
                    + "    已暂停 · 空格继续"
                )
            else:
                state["pause_acc"] += time.time() - state["pause_at"]
                state["paused"] = False
                if music:
                    music.resume()
                root.after(33, tick)
        elif event.keysym in ("Escape", "q"):
            if not state["done"]:
                finish()
            stop_music()
            root.destroy()
        elif event.keysym in ("m", "M"):
            if music is None:
                return
            if music.paused or not music.playing:
                if not music.playing:
                    music.start()
                    state["music_started"] = True
                else:
                    music.resume()
            else:
                music.pause()

    def on_close() -> None:
        stop_music()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.bind("<Key>", on_key)
    root.after(600, begin)
    try:
        root.mainloop()
    finally:
        stop_music()


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def compose_video_frame(
    painter: Painter,
    banner_w: int,
    banner_h: int,
    sub_h: int,
    bar_h: int,
    title_a: float,
    sub_a: float,
    pct: float,
    elapsed: float,
    remain: float,
) -> Image.Image:
    """合成与 GUI 一致的一帧：题匾 + 画布 + 底部进度。"""
    cw, ch = painter.w, painter.h
    # 宽度取画布与题匾较大者
    W = max(cw, banner_w)
    if W % 2:
        W += 1
    H = banner_h + sub_h + ch + bar_h
    if H % 2:
        H += 1

    frame = Image.new("RGB", (W, H), UI_BG)
    banner = render_calligraphy_banner("致敬马拉多纳", width=W, height=banner_h, alpha=title_a)
    sub = render_subtitle(W, alpha=sub_a)
    frame.paste(banner, (0, 0))
    frame.paste(sub, (0, banner_h))

    canvas = painter.snapshot()
    if canvas.size != (cw, ch):
        canvas = canvas.resize((cw, ch), Image.Resampling.BILINEAR)
    ox = (W - cw) // 2
    frame.paste(canvas, (ox, banner_h + sub_h))

    # 底部进度条区域
    bar_y0 = banner_h + sub_h + ch
    draw = ImageDraw.Draw(frame)
    # 进度文字
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
    except OSError:
        font = ImageFont.load_default()
    el_m, el_s = divmod(max(0, int(elapsed)), 60)
    re_m, re_s = divmod(max(0, int(remain)), 60)
    txt = f"进度  {pct:4.0f}%    已用 {el_m}:{el_s:02d} / 剩余 {re_m}:{re_s:02d}"
    bbox = draw.textbbox((0, 0), txt, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, bar_y0 + 6), txt, font=font, fill=(212, 184, 150))

    # 进度条
    margin = 40
    track_y = bar_y0 + bar_h - 18
    track_h = 8
    x0, x1 = margin, W - margin
    draw.rounded_rectangle([x0, track_y, x1, track_y + track_h], radius=3, fill=(50, 40, 38))
    fill_w = int((x1 - x0) * max(0.0, min(1.0, pct / 100.0)))
    if fill_w > 2:
        draw.rounded_rectangle(
            [x0, track_y, x0 + fill_w, track_y + track_h],
            radius=3,
            fill=CINNABAR,
        )
    return frame


def export_mp4(
    painter: Painter,
    duration_s: float,
    music_path: Path | None,
    music_rate: float,
    out_path: Path,
    fps: float = 24.0,
    seed: int = 42,
) -> Path:
    """
    将扫描写生全过程导出为 maradona.mp4（含配乐，墙钟同步）。
    帧通过管道送入 ffmpeg，不落盘中间帧。
    """
    if not shutil_which("ffmpeg"):
        raise RuntimeError("未找到 ffmpeg，请先安装: brew install ffmpeg")

    total = len(painter.ops)
    n_frames = max(1, int(round(duration_s * fps)))
    banner_h, sub_h, bar_h = 72, 28, 48
    banner_w = max(painter.w, 720)

    # 预合成一帧以确定分辨率
    sample = compose_video_frame(
        painter, banner_w, banner_h, sub_h, bar_h, 0.0, 0.0, 0.0, 0.0, duration_s
    )
    vw, vh = sample.size
    print(f"  导出视频: {out_path}")
    print(f"  分辨率:   {vw}×{vh}  fps={fps:.0f}  帧数={n_frames}  时长={duration_s:.0f}s")

    # 音频滤镜：对齐呈现时长
    audio_args: list[str] = []
    if music_path and music_path.is_file():
        rate = max(0.5, min(2.0, music_rate))
        audio_args = [
            "-i",
            str(music_path),
            "-filter:a",
            f"atempo={rate:.5f}",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
        ]
        print(f"  配乐:     {music_path.name}  atempo={rate:.3f}")
    else:
        print("  配乐:     无（仅画面）")

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-stats",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{vw}x{vh}",
        "-r",
        str(fps),
        "-i",
        "-",
        *audio_args,
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-t",
        f"{duration_s:.3f}",
        "-movflags",
        "+faststart",
    ]
    if music_path and music_path.is_file():
        cmd += ["-shortest"]
    cmd.append(str(out_path))

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    assert proc.stdin is not None

    # 缓存题匾，避免每帧重绘书法
    banner_cache: dict[float, Image.Image] = {}
    sub_cache: dict[float, Image.Image] = {}

    def cached_banner(a: float) -> Image.Image:
        k = round(a, 2)
        if k not in banner_cache:
            banner_cache[k] = render_calligraphy_banner(
                "致敬马拉多纳", width=vw, height=banner_h, alpha=k
            )
        return banner_cache[k]

    def cached_sub(a: float) -> Image.Image:
        k = round(a, 2)
        if k not in sub_cache:
            sub_cache[k] = render_subtitle(vw, alpha=k)
        return sub_cache[k]

    t0 = time.time()
    try:
        for fi in range(n_frames):
            t = (fi + 1) / n_frames
            target_i = min(total, int(total * t))
            if target_i > painter.i:
                painter.apply_range(painter.i, target_i)

            title_a = 0.0 if t < 0.05 else min(1.0, (t - 0.05) / 0.23)
            sub_a = 0.0 if t < 0.18 else min(1.0, (t - 0.18) / 0.24)
            elapsed = t * duration_s
            remain = max(0.0, duration_s - elapsed)
            pct = painter.i / max(1, total) * 100

            # 快速合成（用缓存题匾）
            frame = Image.new("RGB", (vw, vh), UI_BG)
            frame.paste(cached_banner(title_a), (0, 0))
            frame.paste(cached_sub(sub_a), (0, banner_h))
            ox = (vw - painter.w) // 2
            # 直接贴画布，避免每帧 copy
            frame.paste(painter.canvas, (ox, banner_h + sub_h))

            draw = ImageDraw.Draw(frame)
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
            except OSError:
                font = ImageFont.load_default()
            el_m, el_s = divmod(max(0, int(elapsed)), 60)
            re_m, re_s = divmod(max(0, int(remain)), 60)
            txt = f"进度  {pct:4.0f}%    已用 {el_m}:{el_s:02d} / 剩余 {re_m}:{re_s:02d}"
            bbox = draw.textbbox((0, 0), txt, font=font)
            tw = bbox[2] - bbox[0]
            bar_y0 = banner_h + sub_h + painter.h
            draw.text(((vw - tw) // 2, bar_y0 + 6), txt, font=font, fill=(212, 184, 150))
            margin = 40
            track_y = bar_y0 + bar_h - 18
            track_h = 8
            x0, x1 = margin, vw - margin
            draw.rectangle([x0, track_y, x1, track_y + track_h], fill=(50, 40, 38))
            fill_w = int((x1 - x0) * max(0.0, min(1.0, pct / 100.0)))
            if fill_w > 2:
                draw.rectangle(
                    [x0, track_y, x0 + fill_w, track_y + track_h],
                    fill=CINNABAR,
                )

            proc.stdin.write(frame.tobytes())

            if (fi + 1) % max(1, n_frames // 20) == 0 or fi + 1 == n_frames:
                print(
                    f"\r  编码进度 {(fi+1)/n_frames*100:5.1f}%  "
                    f"帧 {fi+1}/{n_frames}  {time.time()-t0:.1f}s",
                    end="",
                    flush=True,
                )
        proc.stdin.close()
        stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
        rc = proc.wait(timeout=1200)
        print()
        if rc != 0:
            raise RuntimeError(f"ffmpeg 失败 (code={rc}): {stderr[-800:]}")
    except Exception:
        try:
            proc.kill()
        except OSError:
            pass
        raise

    # 收尾保存静帧成图
    if painter.i < total:
        painter.apply_range(painter.i, total)
    final = painter.final_image()
    save_hd_png(final, OUT_FINAL)
    print(f"  ✓ 视频: {out_path}  ({out_path.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"  ✓ 成图: {OUT_FINAL}")
    return out_path


def shutil_which(cmd: str) -> str | None:
    from shutil import which

    return which(cmd)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="致敬马拉多纳 · 扫描写生")
    p.add_argument("--src", type=Path, default=SRC_DEFAULT)
    p.add_argument("--scale", type=float, default=1.0)
    p.add_argument(
        "--duration",
        type=float,
        default=None,
        help=f"墙钟秒数（默认 {PRESENTATION_DEFAULT_S:.0f}s，上限 {PRESENTATION_MAX_S:.0f}s）",
    )
    p.add_argument("--music", type=Path, default=None)
    p.add_argument("--no-music", action="store_true")
    p.add_argument("--headless", action="store_true")
    p.add_argument("--save-frames", action="store_true")
    p.add_argument(
        "--export-mp4",
        action="store_true",
        help=f"导出完整作品视频到 {OUT_MP4.name}",
    )
    p.add_argument("--fps", type=float, default=24.0, help="导出视频帧率（默认 24）")
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.src.is_file():
        print(f"找不到参考图: {args.src}", file=sys.stderr)
        return 1

    # 启动时先清掉上次崩溃残留的配乐
    kill_orphan_music(verbose=True)

    headless = args.headless
    if not headless and sys.platform != "darwin" and not os.environ.get("DISPLAY"):
        headless = True

    music_path = None if args.no_music else resolve_music_path(args.music)
    music_dur = probe_audio_duration(music_path) if music_path else None
    duration_s, music_rate = compute_presentation_duration(music_dur, args.duration)

    print("=" * 56)
    print("  致敬马拉多纳  ·  扫描写生 · LIFE IS LIFE")
    print("=" * 56)
    print(f"  参考图: {args.src}")
    print(f"  倍率:   {args.scale}x")
    print(f"  呈现:   {duration_s:.1f}s  墙钟同步  (默认/上限 {PRESENTATION_MAX_S:.0f}s)")
    print(f"  模式:   {'无界面' if headless else '动态窗口'}")
    print("  画法:   淡洗 → 横向扫描 → 纵向扫描 → 像素锁定")
    if music_path:
        print(
            f"  配乐:   {music_path.name}  原长 {music_dur:.1f}s  "
            f"播放速率 {music_rate:.3f}×  → 约 {music_dur/music_rate:.1f}s"
            if music_dur
            else f"  配乐:   {music_path}"
        )
    else:
        print("  配乐:   关" if args.no_music else "  配乐:   未找到 mp3")
    print()

    source = load_source(args.src, args.scale)
    w, h = source.size
    print(f"  画布:   {w}×{h}")

    rng = random.Random(args.seed)
    print("  规划扫描路径…")
    ops = make_scan_plan(w, h, rng)
    print(f"  扫描步: {len(ops)}")
    print()

    painter = Painter(source, ops)

    if args.export_mp4:
        print("  模式:   导出 maradona.mp4")
        print()
        try:
            export_mp4(
                painter,
                duration_s,
                music_path if not args.no_music else None,
                music_rate,
                OUT_MP4,
                fps=args.fps,
                seed=args.seed,
            )
        except Exception as e:
            print(f"❌ 导出失败: {e}", file=sys.stderr)
            return 1
        return 0

    music = (
        BackgroundMusic(music_path, rate=music_rate)
        if (music_path and not headless)
        else None
    )

    if headless:
        final = run_headless(painter, duration_s, args.save_frames)
        save_hd_png(final, OUT_FINAL)
        print(f"✓ 已保存 {OUT_FINAL}")
    else:
        run_gui(painter, duration_s, args.save_frames, music=music)

    print()
    print("  空格暂停  M 静音  Esc 结束")
    print(f"  导出视频: python Maradona/draw_maradona.py --export-mp4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
