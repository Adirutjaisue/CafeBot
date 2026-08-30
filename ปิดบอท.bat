@echo off
chcp 65001 >nul
title Gamers' Cafe Discord Bot - Stop Service
color 0C
echo ================================================================
echo               🛑 ปิดการทำงานบอท GAMERS' CAFE 🎮
echo ================================================================
echo.
echo [*] กำลังค้นหาและปิดโปรเซสบอทในเครื่อง...

:: ปิดหน้าต่างรันบอทและโปรเซส Python ที่รันบอทตัวนี้
taskkill /F /FI "WINDOWTITLE eq Gamers' Cafe Discord Bot*" /T >nul 2>&1
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*src\bot.py*' -or $_.CommandLine -like '*Discord\CafeBot*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1

echo.
echo [OK] ปิดการทำงานของบอทในเครื่องคอมพิวเตอร์เรียบร้อยแล้วครับ!
echo.
echo กดปุ่มใดๆ เพื่อปิดหน้าต่างนี้...
pause >nul
