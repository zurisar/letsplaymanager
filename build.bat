@echo off
chcp 65001 >nul
echo Начинаем компиляцию LetsPlayManager...

:: 1. Удаляем старые сборки, чтобы не было конфликтов
rmdir /s /q "build"
rmdir /s /q "dist"

:: 2. Компилируем чистый код
pyinstaller --noconsole --onedir --name "LetsPlayManager" main.py

:: 3. Копируем внешние файлы прямо в корень собранной программы
echo Копирование внешних ресурсов...
xcopy /E /I /Y "lang" "dist\LetsPlayManager\lang"
xcopy /E /I /Y "bin" "dist\LetsPlayManager\bin"
copy /Y "*.txt" "dist\LetsPlayManager\"

echo.
echo Сборка успешно завершена! Папка dist готова.
pause
