# FX 自動フォローBot

X（旧Twitter）でFX関連の発言をしているユーザーを1日最大200人自動フォローするBot。

---

## Windows セットアップ手順

### ステップ1: Python をインストール

https://python.org/downloads から最新版をダウンロード。

インストール時に **「Add Python to PATH」にチェックを入れる**（重要）。

### ステップ2: コードをダウンロード

コマンドプロンプト（cmd）を開いて：

```cmd
cd C:\Users\snoob\Desktop
git clone https://github.com/snoopykun1221/snoopykun1221
cd snoopykun1221
```

> git が入っていない場合は https://git-scm.com からインストール。

### ステップ3: ライブラリをインストール

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### ステップ4: .env ファイルを作成

`snoopykun1221` フォルダの中に `.env` というファイルを作り、以下を記入：

```
X_USERNAME=あなたのXのID
X_PASSWORD=あなたのパスワード
X_EMAIL=あなたのメールアドレス
HEADLESS=false
```

### ステップ5: 動作確認

```cmd
.venv\Scripts\activate
python fx_auto_follow.py
```

ブラウザが開いてXにログインし、自動でフォローが始まればOKです。

### ステップ6: タスクスケジューラで毎日自動実行

`run.bat` がフォルダに含まれています。パスを自分の環境に合わせて確認してください。

タスクスケジューラの設定手順：

1. Windowsキー →「タスクスケジューラ」と検索して開く
2. 右側の「基本タスクの作成」をクリック
3. 名前：`FX自動フォロー` → 次へ
4. トリガー：「毎日」→ 次へ
5. 開始時刻：`9:00` → 次へ
6. 操作：「プログラムの開始」→ 次へ
7. プログラム：`run.bat` のフルパスを指定 → 完了

> **注意**: PCがスリープ状態だと動かないため、設定 → 電源 → スリープを「なし」または「4時間以上」に変更しておくと安心です。

---

## 設定項目（.env）

| 変数 | 説明 | デフォルト |
|------|------|-----------|
| `X_USERNAME` | XのIDまたはメールアドレス | 必須 |
| `X_PASSWORD` | Xのパスワード | 必須 |
| `X_EMAIL` | 2段階認証時のメールアドレス | 任意 |
| `HEADLESS` | ブラウザを非表示で実行 (`true`/`false`) | `false` |
| `DAILY_FOLLOW_LIMIT` | 1日のフォロー上限 | `200` |
| `FOLLOW_DELAY_MIN` | フォロー間隔 最小（秒） | `30` |
| `FOLLOW_DELAY_MAX` | フォロー間隔 最大（秒） | `90` |

---

## ログ・状態ファイル

- `fx_follow.log` — 実行ログ
- `follow_state.json` — フォロー済みユーザーと日別カウント
- `x_cookies.json` — ログインセッション保存（再ログイン省略用）
