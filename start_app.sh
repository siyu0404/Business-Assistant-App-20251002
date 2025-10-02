#!/bin/bash
# 進入你的專案目錄
cd "$(dirname "$0")"

# 啟動虛擬環境
source venv/bin/activate

# 執行主程式
python3 main_gui.py