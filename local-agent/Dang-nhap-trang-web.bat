@echo off
rem Helper cho khach: double-click, dan link trang web, Enter -> cua so dang nhap.
rem Copy file nay vao thu muc dist/PersonalAgent/ khi dong goi gui khach.
chcp 65001 >nul
cd /d "%~dp0"
echo ==============================================
echo   DANG NHAP TRANG WEB CHO PERSONAL AGENT
echo   (dang nhap 1 lan, phien luu tren may ban)
echo ==============================================
echo.
set /p URL="Dan link trang web can dang nhap roi bam Enter: "
PersonalAgent.exe --login %URL%
pause
