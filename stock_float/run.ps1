# 一键启动看盘悬浮球
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
& "$root\.venv\Scripts\python.exe" "$root\main.py"