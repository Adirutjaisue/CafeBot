@echo off
chcp 65001 >nul
title Gamers' Cafe Discord Bot
color 0A
echo ================================================================
echo               ☕ GAMERS' CAFE DISCORD BOT 🎮
echo ================================================================
echo.
echo [*] กำลังเริ่มทำงานบอท...
cd /d "%~dp0"
python src\bot.py
echo.
echo [!] บอทหยุดทำงานแล้ว กดปุ่มใดๆ เพื่อปิดหน้าต่างนี้
pause >nul
