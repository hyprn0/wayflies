# 🦋 hyprn-butterfly

Пиксельная переливающаяся 2.5D-бабочка, которая летает по рабочему столу Wayland.

- Маленькая 3D-модель (тельце + два крыла на шарнирах) с пиксель-арт текстурой, отрисованная обратно в пиксельную сетку.
- Поворачивается носом по курсу полёта, кренится на виражах, машет крыльями в объёме.
- Цвет крыльев переливается (бирюзовый → синий → фиолетовый → розовый) и зависит от угла к «камере», как у настоящей морфо.
- Живёт на прозрачном слое над обоями, клики проходят сквозь слой — кликабельна только сама бабочка.
- Подведёшь курсор — улетит, иногда садится отдохнуть. Клик по ней — россыпь искр.

## Требования

- Wayland-композитор с поддержкой `wlr-layer-shell`: **Hyprland**, Sway, river и т. п. (GNOME/Mutter не подходит).
- Python 3
- GTK 3, PyGObject, pycairo, gtk-layer-shell

## Установка

### 1. Зависимости

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

### 2. Скачать

```bash
git clone https://github.com/<твой-ник>/hyprn-butterfly.git ~/.local/share/hyprn-butterfly
```

### 3. Запустить

```bash
~/.local/share/hyprn-butterfly/butterfly.sh start
```

Остановить: `butterfly.sh stop`, включить/выключить одной командой: `butterfly.sh toggle`.

Лог пишется в `/tmp/hyprn-butterfly.log` — туда смотреть, если бабочка не появилась.

## Автозапуск в Hyprland

В `~/.config/hypr/hyprland.conf`:

```ini
exec-once = ~/.local/share/hyprn-butterfly/butterfly.sh start

# по желанию — переключатель на клавишу
bind = $mainMod, B, exec, ~/.local/share/hyprn-butterfly/butterfly.sh toggle
```

Для Sway: `exec ~/.local/share/hyprn-butterfly/butterfly.sh start` в `~/.config/sway/config`.

## Настройки

Задаются переменными окружения:

| Переменная | По умолчанию | Описание |
|---|---|---|
| `BUTTERFLIES` | `1` | Сколько бабочек (1–8). У каждой свой оттенок. |
| `BUTTERFLY_PX` | `4` | Размер «пикселя». Больше — крупнее и «пикселистее». |
| `BUTTERFLY_LAYER` | `bottom` | `bottom` — летает только по рабочему столу, под окнами; `top` — поверх всех окон. |

Пример:

```bash
BUTTERFLIES=3 BUTTERFLY_PX=5 BUTTERFLY_LAYER=top ~/.local/share/hyprn-butterfly/butterfly.sh start
```

В Hyprland:

```ini
exec-once = env BUTTERFLIES=2 BUTTERFLY_PX=5 ~/.local/share/hyprn-butterfly/butterfly.sh start
```

## Решение проблем

**`layer-shell не поддерживается`** — композитор не поддерживает `wlr-layer-shell` (например, GNOME) или программа запущена не под Wayland.

**`ImportError` / `Namespace GtkLayerShell not found`** — не установлены зависимости из шага 1.

**Падает или окно не появляется, хотя зависимости стоят** — известная особенность `gtk-layer-shell`: библиотеку нужно подгрузить раньше `libwayland`. Запусти так (путь может отличаться, смотри `pacman -Ql gtk-layer-shell` / `dpkg -L`):
```bash
LD_PRELOAD=/usr/lib/libgtk-layer-shell.so python3 butterfly.py
```

**Бабочки не видно** — по умолчанию она на слое `bottom`, и все окна её закрывают. Покажи рабочий стол или запусти с `BUTTERFLY_LAYER=top`.

**Бабочка на другом мониторе** — используется основной монитор.

**Обои с программой типа swww/hyprpaper** — должны быть на слое `background`, тогда бабочка летает над ними.

## Удаление

```bash
~/.local/share/hyprn-butterfly/butterfly.sh stop
rm -rf ~/.local/share/hyprn-butterfly
```
и убери строки из `hyprland.conf`.

## Как это устроено

Крылья описаны ASCII-текстурой в `butterfly.py` (`LEFT`, `BODY`): `k` — контур, `a` — крыло с переливом, `b` — тёмная часть, `w` — блики. Правое крыло зеркальное. Модель проецируется с наклоном камеры ~29° с z-буфером в пиксельную сетку, поэтому крылья выглядят объёмными. Можно нарисовать свою бабочку, поменяв эти строки.

Метка слоя (namespace) — `hyprn-butterfly`, её можно использовать в `layerrule` Hyprland.
