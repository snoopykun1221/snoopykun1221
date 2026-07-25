@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ================================
echo   リール保存を起動します
echo ================================
echo.

REM Node.js が入っているか確認
where node >nul 2>nul
if errorlevel 1 (
  echo [エラー] Node.js が見つかりません。
  echo https://nodejs.org からインストールしてから、もう一度このファイルを実行してください。
  echo.
  pause
  exit /b 1
)

REM 初回のみ依存関係をインストール
if not exist "node_modules" (
  echo 初回セットアップ中です。少しお待ちください...
  call npm install
  echo.
)

REM 数秒後にブラウザを自動で開く
start "" /min cmd /c "timeout /t 3 >nul & start http://localhost:3000"

echo ブラウザで http://localhost:3000 を開きます。
echo このウィンドウを閉じるとサイトは停止します。
echo.
npm start

pause
