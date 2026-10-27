#!/bin/bash
# Бабочка на рабочем столе: ./butterfly.sh start | stop | toggle
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
PAT="$DIR/butterfly.py"

case "${1:-toggle}" in
  start)
    pgrep -f "$PAT" >/dev/null && exit 0
    nohup python3 "$PAT" >/tmp/hyprn-butterfly.log 2>&1 &
    disown
    ;;
  stop)
    pkill -f "$PAT"
    ;;
  toggle)
    if pgrep -f "$PAT" >/dev/null; then "$0" stop; else "$0" start; fi
    ;;
  *)
    echo "usage: $0 start|stop|toggle"; exit 1
    ;;
esac
