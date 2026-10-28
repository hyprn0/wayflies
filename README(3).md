# 🦋 wayflies

A pixelated, iridescent 2.5D butterfly that flutters around your Wayland desktop.

- A tiny 3D model (body + two hinged wings) with a pixel-art texture, rendered back onto a pixel grid.
- Turns its nose along its flight path, banks in turns, and flaps its wings in 3D.
- Wing color shimmers (turquoise → blue → violet → pink) and depends on the angle to the "camera", like a real morpho.
- Lives on a transparent layer above your wallpaper; clicks pass straight through the layer — only the butterfly itself is clickable.
- Move your cursor close and it flies away, and sometimes it lands to rest. Click it for a burst of sparks.

## Requirements

- A Wayland compositor with `wlr-layer-shell` support: **Hyprland**, Sway, river, etc. (GNOME/Mutter will not work).
- Python 3
- GTK 3, PyGObject, pycairo, gtk-layer-shell

## Installation

### 1. Dependencies

**Arch / Manjaro / EndeavourOS**
```bash
sudo pacman -S --needed python-gobject python-cairo gtk3 gtk-layer-shell
```

**Debian / Ubuntu**
```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-gtklayershell-0.1
```

**Fedora**
```bash
sudo dnf install python3-gobject python3-cairo gtk3 gtk-layer-shell
```

### 2. Download

```bash
git clone https://github.com/<your-username>/wayflies.git ~/.local/share/wayflies
```

### 3. Run

```bash
~/.local/share/wayflies/butterfly.sh start
```

Stop it with `butterfly.sh stop`, or turn it on/off with a single command: `butterfly.sh toggle`.

The log is written to `/tmp/wayflies.log` — check it if the butterfly doesn't show up.

## Autostart in Hyprland

In `~/.config/hypr/hyprland.conf`:

```ini
exec-once = ~/.local/share/wayflies/butterfly.sh start

# optional — bind a toggle to a key
bind = $mainMod, B, exec, ~/.local/share/wayflies/butterfly.sh toggle
```

For Sway: `exec ~/.local/share/wayflies/butterfly.sh start` in `~/.config/sway/config`.

## Configuration

Set via environment variables:

| Variable | Default | Description |
|---|---|---|
| `BUTTERFLIES` | `1` | How many butterflies (1–8). Each has its own hue. |
| `BUTTERFLY_PX` | `4` | Size of one "pixel". Larger means bigger and more pixelated. |
| `BUTTERFLY_LAYER` | `bottom` | `bottom` — flies only over the desktop, under windows; `top` — above all windows. |

Example:

```bash
BUTTERFLIES=3 BUTTERFLY_PX=5 BUTTERFLY_LAYER=top ~/.local/share/wayflies/butterfly.sh start
```

In Hyprland:

```ini
exec-once = env BUTTERFLIES=2 BUTTERFLY_PX=5 ~/.local/share/wayflies/butterfly.sh start
```

## Troubleshooting

**`layer-shell is not supported`** — your compositor doesn't support `wlr-layer-shell` (e.g. GNOME), or the program isn't running under Wayland.

**`ImportError` / `Namespace GtkLayerShell not found`** — the dependencies from step 1 aren't installed.

**Crashes or no window appears even though the dependencies are installed** — a known quirk of `gtk-layer-shell`: the library must be loaded before `libwayland`. Run it like this (the path may differ; check `pacman -Ql gtk-layer-shell` / `dpkg -L`):
```bash
LD_PRELOAD=/usr/lib/libgtk-layer-shell.so python3 butterfly.py
```

**Can't see the butterfly** — by default it's on the `bottom` layer, so every window covers it. Show the desktop or run with `BUTTERFLY_LAYER=top`.

**Butterfly is on the wrong monitor** — the primary monitor is used.

**Wallpaper programs like swww/hyprpaper** — they must be on the `background` layer so the butterfly can fly above them.

## Uninstall

```bash
~/.local/share/wayflies/butterfly.sh stop
rm -rf ~/.local/share/wayflies
```
and remove the lines from `hyprland.conf`.

## How it works

The wings are described by ASCII textures in `butterfly.py` (`LEFT`, `BODY`): `k` — outline, `a` — iridescent wing, `b` — dark part, `w` — highlights. The right wing is a mirror image. The model is projected with a ~29° camera tilt and a z-buffer onto the pixel grid, which is why the wings look volumetric. You can draw your own butterfly by editing those lines.

The layer namespace is `wayflies`; you can use it in Hyprland `layerrule`s.
