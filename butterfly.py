#!/usr/bin/env python3
"""Hyprn butterfly — пиксельная переливающаяся 2.5D-бабочка, которая летает по рабочему столу.

Бабочка — маленькая 3D-модель (тельце + два крыла на шарнирах), текстура крыльев — пиксель-арт.
Она поворачивается туда, куда летит, кренится в виражах и машет крыльями в объёме; смотрим
на неё сверху под углом, а картинка собирается обратно в пиксельную сетку.
Цвет крыла зависит от угла к «камере» — как у настоящей морфо.

Живёт на прозрачном слое над обоями и eww-виджетами, но под окнами. Клики проходят
сквозь слой — кликабельна только сама бабочка. Подведёшь курсор — улетит, иногда садится.

Настройки через переменные окружения:
    BUTTERFLIES=2         сколько бабочек (по умолчанию 1)
    BUTTERFLY_PX=5        размер «пикселя» (по умолчанию 4)
    BUTTERFLY_LAYER=top   летать поверх окон (по умолчанию bottom — только по рабочему столу)

Зависимости (Arch, обычно уже стоят вместе с eww):
    sudo pacman -S --needed python-gobject python-cairo gtk-layer-shell
"""
import colorsys
import math
import os
import random
import signal
import sys
import time

try:
    import cairo
except ImportError:
    cairo = None

PX = max(1, int(os.environ.get("BUTTERFLY_PX", "4")))
COUNT = max(1, min(8, int(os.environ.get("BUTTERFLIES", "1"))))
LAYER = os.environ.get("BUTTERFLY_LAYER", "bottom")

# ============================== модель ==============================
# Текстура левого крыла (10 пикселей, справа — тельце); правое — зеркальное.
# Строка 0 — нос. k — контур, a — крыло (перелив), b — тёмная часть крыла, w — блики.
LEFT = ["..kk....k.",
        ".kaak....k",
        "kaaaakk...",
        "kawaaaakk.",
        "kaaabaaaak",
        "kaabbbaaak",
        ".kaabbbbak",
        "..kkaabbak",
        "...kkkkkkk",
        "...kaabbak",
        "..kaaabbak",
        ".kawaabbak",
        ".kaaaaabk.",
        "..kaaaak..",
        "...kkkk..."]
BODY = "..kmmmmmmmmmk.."          # тельце по строкам: m — тельце, k — голова/кончик
FIXED = {"k": (0.04, 0.06, 0.10), "m": (0.13, 0.09, 0.22)}
CAM = 0.5                          # наклон «камеры» от вертикали, рад (~29°)
CA, SA = math.cos(CAM), math.sin(CAM)
SUB = ((0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75))
RADIUS = 13                        # радиус модели в пикселях-клетках (для областей перерисовки)


def build_model():
    """Точки модели: (вперёд, от тела, сторона, вид, символ, i, j)."""
    pts = []
    for j, half in enumerate(LEFT):
        for i, ch in enumerate(half):
            if ch == ".":
                continue
            kind = "ant" if j <= 1 and i >= 6 else "wing"
            for du, dv in SUB:
                s = (9 - i) + du + 0.5
                f = 7.0 - (j + dv)
                for side in (-1, 1):
                    pts.append((f, s, side, kind, ch, i if side < 0 else 20 - i, j))
        if BODY[j] != ".":
            for dv in (0.25, 0.75):
                for ds in (-0.25, 0.25):
                    pts.append((7.0 - (j + dv), ds, 0, "body", BODY[j], 10, j))
    return pts


MODEL = build_model()


def wing_rgb(ch, i, j, t, phase, hue0, facing):
    wave = math.sin(t * 1.7 + i * 0.32 + j * 0.21)
    # волна бежит по крылу, весь цвет гуляет бирюзовый → синий → фиолетовый → розовый,
    # а под косым углом к «камере» крыло уходит в фиолетовый (структурный цвет)
    h = (hue0 + 0.10 * wave + 0.15 * math.sin(t * 0.35 + hue0 * 6) + 0.05 * math.sin(t * 1.1)
         + 0.14 * (1 - facing)) % 1.0
    light = 0.62 + 0.38 * facing
    if ch == "a":
        l, s = (0.52 + 0.06 * wave) * light + 0.08 * facing, 0.95
    elif ch == "b":
        h, l, s = (h + 0.09) % 1.0, 0.34 * light + 0.04, 0.9
    else:                                           # w
        l, s = 0.82 * light + 0.12, 0.6
    return colorsys.hls_to_rgb(h, max(0.0, min(1.0, l)), s)


def render_cells(b, t):
    """Проецирует модель в пиксельную сетку. Возвращает {(cx, cy): rgb} и множество клеток тени."""
    ch_, sh_ = math.cos(b.heading), math.sin(b.heading)
    F = (ch_, sh_, 0.0)
    R0 = (-sh_, ch_, 0.0)
    cb, sb = math.cos(b.bank), math.sin(b.bank)
    R = (R0[0] * cb, R0[1] * cb, sb)                  # крен вокруг продольной оси
    U = (-R0[0] * sb, -R0[1] * sb, cb)
    ct, st = math.cos(b.flap), math.sin(b.flap)
    facing = {}
    for side in (-1, 1):                              # нормаль крыла → насколько оно смотрит в «камеру»
        wd = tuple(R[k] * side * ct + U[k] * st for k in range(3))
        n = (F[1] * wd[2] - F[2] * wd[1], F[2] * wd[0] - F[0] * wd[2], F[0] * wd[1] - F[1] * wd[0])
        facing[side] = abs(n[1] * SA + n[2] * CA)
    zbuf, cols, shadow = {}, {}, set()
    cache = {}
    for f, s, side, kind, ch, i, j in MODEL:
        if kind == "wing":
            ls, lu = side * s * ct, s * st
        elif kind == "ant":
            ls, lu = side * s * 0.8, s * 0.35 + 0.6
        else:
            ls, lu = s, 0.25
        wx = F[0] * f + R[0] * ls + U[0] * lu
        wy = F[1] * f + R[1] * ls + U[1] * lu
        wz = R[2] * ls + U[2] * lu
        key = (math.floor(wx), math.floor(wy * CA - wz * SA))
        depth = wz * CA + wy * SA
        if key not in zbuf or depth > zbuf[key]:
            zbuf[key] = depth
            ck = (ch, i, j, kind)
            if ck not in cache:
                if ch in FIXED:
                    cache[ck] = FIXED[ch]
                else:
                    cache[ck] = wing_rgb(ch, i, j, t, b.phase, b.hue, facing[side] if side else 1.0)
            cols[key] = cache[ck]
        shadow.add((math.floor(wx), math.floor(wy)))
    return cols, shadow


# ============================== поведение ==============================
def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


class Butterfly:
    SPEED = 110.0

    def __init__(self, W, H, rng, hue):
        self.rng, self.W, self.H, self.hue = rng, W, H, hue
        self.x, self.y = rng.uniform(80, W - 80), rng.uniform(80, H - 160)
        self.vx = self.vy = 0.0
        self.heading, self.bank, self.flap = rng.uniform(-math.pi, math.pi), 0.0, 0.4
        self.state, self.rest_until, self.flee_until = "fly", 0.0, 0.0
        self.phase, self.seed, self.spark_acc = 0.0, rng.random() * 10, 0.0
        self.height = 1.0                              # 0 — сидит, 1 — летит (для тени)
        self.pick_target()

    def bbox(self, pad=0):
        half = RADIUS * PX
        return (int(self.x - half) - pad, int(self.y - half) - pad,
                2 * half + 2 * pad + 4 * PX, 2 * half + 2 * pad + 9 * PX)

    def hitbox(self):
        half = 9 * PX
        return (int(self.x - half), int(self.y - half), 2 * half, 2 * half)

    def pick_target(self, away_from=None):
        best = None
        for _ in range(12):
            tx, ty = self.rng.uniform(60, self.W - 60), self.rng.uniform(60, self.H - 150)
            d = math.hypot(tx - self.x, ty - self.y)
            if away_from:
                d = math.hypot(tx - away_from[0], ty - away_from[1])
            if best is None or d > best[0]:
                best = (d, tx, ty)
            if not away_from and d > 220:
                break
        self.tx, self.ty = best[1], best[2]

    def scare(self, t, px, py):
        self.state = "fly"
        self.flee_until = t + 1.2
        self.pick_target(away_from=(px, py))

    def update(self, t, dt, sparks):
        if self.state == "rest":
            self.phase += dt * 1.6
            self.flap = 0.25 + 0.95 * (0.5 + 0.5 * math.sin(self.phase))   # медленно складывает крылья
            self.bank += (0 - self.bank) * min(1.0, dt * 4)
            self.height = max(0.0, self.height - dt * 2)
            if t >= self.rest_until:
                self.state = "fly"
                self.pick_target()
            return
        self.height = min(1.0, self.height + dt * 2)
        fleeing = t < self.flee_until
        speed = self.SPEED * (3.2 if fleeing else 1.0) * (0.85 + 0.25 * math.sin(t * 0.8 + self.seed))
        dx, dy = self.tx - self.x, self.ty - self.y
        dist = math.hypot(dx, dy)
        if dist < 25:
            if not fleeing and self.rng.random() < 0.25:
                self.state, self.rest_until = "rest", t + self.rng.uniform(3, 8)
                self.vx = self.vy = 0.0
                self.phase = -math.pi / 2
                return
            self.pick_target()
            dx, dy = self.tx - self.x, self.ty - self.y
            dist = max(1.0, math.hypot(dx, dy))
        k = min(1.0, dt * (5.0 if fleeing else 2.2))
        self.vx += (dx / dist * speed - self.vx) * k
        self.vy += (dy / dist * speed - self.vy) * k
        flutter = math.sin(t * 9 + self.seed) * 38 + math.sin(t * 3.1 + self.seed) * 14
        self.x = min(self.W - 30, max(30, self.x + self.vx * dt))
        self.y = min(self.H - 30, max(30, self.y + (self.vy + flutter) * dt))
        # поворот носом по курсу и крен в вираже
        if math.hypot(self.vx, self.vy) > 15:
            want = math.atan2(self.vy, self.vx)
            rate = (9.0 if fleeing else 4.5) * dt
            turn = max(-rate, min(rate, wrap(want - self.heading)))
            self.heading = wrap(self.heading + turn)
            bank_want = max(-0.8, min(0.8, turn / max(dt, 1e-3) * 0.22))
        else:
            bank_want = 0.0
        self.bank += (bank_want - self.bank) * min(1.0, dt * 6)
        self.phase += dt * 2 * math.pi * (7.0 if fleeing else 4.5)
        self.flap = 0.45 + 0.8 * math.sin(self.phase)                    # взмах: ~-20°…+72°
        self.spark_acc += dt
        step = 0.03 if fleeing else 0.07
        while self.spark_acc > step:
            self.spark_acc -= step
            if len(sparks) < 80:
                bx = self.x - math.cos(self.heading) * 6 * PX + self.rng.uniform(-6, 6)
                by = self.y - math.sin(self.heading) * 6 * PX * CA + self.rng.uniform(-6, 6)
                sparks.append(Spark(bx, by, t, (self.hue + self.rng.uniform(-0.12, 0.12)) % 1.0))


class Spark:
    LIFE = 0.9

    def __init__(self, x, y, born, hue):
        self.x, self.y, self.born, self.hue = x, y, born, hue

    def alive(self, t):
        return t - self.born < self.LIFE

    def pos(self, t):
        return self.x, self.y + (t - self.born) * 18

    def bbox(self, t):
        x, y = self.pos(t)
        return (int(x) - 2 * PX, int(y) - 2 * PX, 5 * PX, 5 * PX)


def burst(b, t, sparks, rng):
    for _ in range(18):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(4, 26)
        sparks.append(Spark(b.x + math.cos(a) * r, b.y + math.sin(a) * r, t, (b.hue + rng.uniform(-0.2, 0.2)) % 1.0))


# ============================== отрисовка ==============================
def snap(v):
    return int(round(v / PX) * PX)


def draw_spark(cr, s, t):
    k = (t - s.born) / s.LIFE
    x, y = s.pos(t)
    x, y = snap(x), snap(y)
    r, g, b = colorsys.hls_to_rgb(s.hue, 0.75, 0.95)
    cr.set_source_rgba(r, g, b, 1 - k)
    cr.rectangle(x, y, PX, PX)
    cr.fill()
    if k < 0.5:                                   # пока свежая — крестиком
        cr.set_source_rgba(r, g, b, (1 - k * 2) * 0.8)
        for ox, oy in ((-PX, 0), (PX, 0), (0, -PX), (0, PX)):
            cr.rectangle(x + ox, y + oy, PX, PX)
        cr.fill()


def draw_butterfly(cr, b, t):
    cols, shadow = render_cells(b, t)
    x0, y0 = snap(b.x), snap(b.y)
    lift = 1 + round(5 * b.height)                 # чем выше летит, тем дальше тень
    cr.set_source_rgba(0, 0, 0, 0.16 + 0.06 * (1 - b.height))
    for cx, cy in shadow:
        cr.rectangle(x0 + (cx + 1) * PX, y0 + (cy + lift) * PX, PX, PX)
    cr.fill()
    for (cx, cy), rgb in cols.items():
        cr.set_source_rgb(*rgb)
        cr.rectangle(x0 + cx * PX, y0 + cy * PX, PX, PX)
        cr.fill()


def union(rects):
    rects = [r for r in rects if r]
    if not rects:
        return None
    x0 = min(r[0] for r in rects); y0 = min(r[1] for r in rects)
    x1 = max(r[0] + r[2] for r in rects); y1 = max(r[1] + r[3] for r in rects)
    return (x0, y0, x1 - x0, y1 - y0)


# ============================== GTK3 + layer-shell (как eww) ==============================
def run():
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import Gtk, Gdk, GLib, GtkLayerShell as LS

    if not LS.is_supported():
        print("layer-shell не поддерживается (нужен Wayland: Hyprland/Sway)", file=sys.stderr)
        sys.exit(1)

    display = Gdk.Display.get_default()
    mon = display.get_primary_monitor() or display.get_monitor(0)
    geo = mon.get_geometry()

    css = Gtk.CssProvider()
    css.load_from_data(b"window, .background { background: transparent; }")
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    win = Gtk.Window()
    win.set_app_paintable(True)
    visual = win.get_screen().get_rgba_visual()
    if visual:
        win.set_visual(visual)
    LS.init_for_window(win)
    LS.set_namespace(win, "hyprn-butterfly")
    LS.set_layer(win, LS.Layer.TOP if LAYER == "top" else LS.Layer.BOTTOM)
    LS.set_monitor(win, mon)
    for edge in (LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.LEFT, LS.Edge.RIGHT):
        LS.set_anchor(win, edge, True)
    LS.set_exclusive_zone(win, -1)
    if hasattr(LS, "set_keyboard_mode"):
        LS.set_keyboard_mode(win, LS.KeyboardMode.NONE)
    else:
        LS.set_keyboard_interactivity(win, False)

    rng = random.Random()
    W, H = geo.width, geo.height
    flies = [Butterfly(W, H, rng, (0.52 + i * 0.13) % 1.0) for i in range(COUNT)]
    sparks = []
    state = {"last": time.monotonic(), "dirty": None}

    da = Gtk.DrawingArea()
    da.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.ENTER_NOTIFY_MASK |
                  Gdk.EventMask.POINTER_MOTION_MASK)

    def on_draw(widget, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)      # cr обрезан областью перерисовки — чистим только её
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        t = time.monotonic()
        for s in sparks:
            draw_spark(cr, s, t)
        for b in sorted(flies, key=lambda b: b.y):
            draw_butterfly(cr, b, t)
        return False

    def nearest(x, y):
        return min(flies, key=lambda b: math.hypot(b.x - x, b.y - y))

    def on_enter(_w, ev):
        nearest(ev.x, ev.y).scare(time.monotonic(), ev.x, ev.y)
        return False

    def on_press(_w, ev):
        t = time.monotonic()
        b = nearest(ev.x, ev.y)
        burst(b, t, sparks, rng)
        b.scare(t, ev.x, ev.y)
        return True

    da.connect("draw", on_draw)
    da.connect("enter-notify-event", on_enter)
    da.connect("motion-notify-event", on_enter)
    da.connect("button-press-event", on_press)
    win.add(da)
    win.show_all()

    def set_input():
        rects = [cairo.RectangleInt(*b.hitbox()) for b in flies]
        win.input_shape_combine_region(cairo.Region(rects))

    set_input()

    def tick():
        t = time.monotonic()
        dt = min(0.05, t - state["last"])
        state["last"] = t
        aw, ah = da.get_allocated_width(), da.get_allocated_height()
        for b in flies:
            if aw > 100 and ah > 100:
                b.W, b.H = aw, ah
            b.update(t, dt, sparks)
        sparks[:] = [s for s in sparks if s.alive(t)]
        new = union([b.bbox(2 * PX) for b in flies] + [s.bbox(t) for s in sparks])
        area = union([state["dirty"], new])
        if area:
            da.queue_draw_area(*area)
        state["dirty"] = new
        set_input()
        return True

    def quit_(*_):
        Gtk.main_quit()
        return False

    GLib.timeout_add(16, tick)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, quit_)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, quit_)
    Gtk.main()


if __name__ == "__main__":
    run()
