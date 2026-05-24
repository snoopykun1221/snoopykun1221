#!/bin/bash
# FX Auto Follow Bot セットアップスクリプト

set -e

echo "=== FX 自動フォローBot セットアップ ==="

# Python 仮想環境作成
python3 -m venv .venv
source .venv/bin/activate

# 依存パッケージインストール
pip install -r requirements.txt

# .env ファイル確認
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "⚠️  .env ファイルを作成しました。"
    echo "   .env を編集してAPIキーを設定してください。"
    echo ""
fi

# cron 設定（毎日9:00に実行）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CRON_JOB="0 9 * * * cd $SCRIPT_DIR && $SCRIPT_DIR/.venv/bin/python fx_auto_follow.py >> fx_follow.log 2>&1"

# 既存のcronに追加されていない場合のみ追加
if crontab -l 2>/dev/null | grep -q "fx_auto_follow.py"; then
    echo "cron ジョブはすでに設定済みです。"
else
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "cron ジョブを設定しました: 毎日 9:00 に実行"
fi

echo ""
echo "=== セットアップ完了 ==="
echo ""
echo "手動実行:"
echo "  source .venv/bin/activate"
echo "  python fx_auto_follow.py"
