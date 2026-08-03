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

---

## note記事自動投稿機能

20代OL投資家向けのnote記事を毎日自動生成して、noteに自動投稿します。

note.comのログインページにはreCAPTCHAがあるため、ログイン自体を毎回自動化することはできません。
そのため、**一度だけ手動でログインしてセッション（Cookie）を保存し、それを自動投稿スクリプトが使い回す**方式を採用しています。

### セットアップ

#### 1. ログインセッションを作成（初回のみ・手動）

```cmd
pip install -r requirements.txt
playwright install chromium
python note_login_setup.py
```

ブラウザが開くので、表示された画面で実際にnoteへログインしてください（reCAPTCHAが出た場合もそのまま手動で完了）。
ログイン後、ターミナルでEnterキーを押すと `note_session.json` が生成されます。

#### 2. `.env` に APIキーを追加

```
ANTHROPIC_API_KEY=your_api_key
```

#### 3. GitHub Secrets を設定（GitHub Actions使用時）

GitHub リポジトリ設定 → Secrets に以下を追加：

- `ANTHROPIC_API_KEY` — Claude APIキー
- `NOTE_SESSION_STATE` — `note_session.json` の内容をそのまま貼り付け

#### 4. ローカルでテスト

いきなり公開せず、まず下書き保存だけを試すことをおすすめします。

```cmd
NOTE_PUBLISH_MODE=draft python note_auto_poster.py   # 下書き保存で止める
python note_auto_poster.py                            # 公開まで実行
```

### 投稿の流れ

`note_auto_poster.py` は、実際のnoteの画面操作を次の順で自動実行します。

1. 保存済みセッションでログイン状態を復元（reCAPTCHA回避のため毎回のログインはしない）
2. Claude APIで記事を生成
3. トップページの「投稿」から `editor.note.com` の新規エディタへ
4. タイトルと本文を入力
5. 「公開に進む」→ 記事タイプ「有料」→ 価格300円
6. 「有料エリア設定」で、見出し「数字で見る、いまの実力」の直前に境界を移動
7. 「投稿する」

**安全のための中断条件**（意図しない形で公開されるのを防ぐため、以下では公開せず失敗終了します）

- 有料設定（300円）ができなかったとき（無料公開の防止）
- 有料エリアの境界が見つからない、または記事の先頭付近と判定されたとき（全文有料の防止）

### セッションの更新

`note_session.json` の有効期限が切れると投稿が失敗し、ログに再作成を促すメッセージが出ます。
その場合は手順1をもう一度実行し、GitHub Secretsの `NOTE_SESSION_STATE` も新しい内容に更新してください。

### 自動実行設定

#### GitHub Actions（推奨・無料）

`.github/workflows/daily_note_poster.yml` で毎日午前8時（UTC）＝日本時間17時に自動実行。

リポジトリのタブで **Actions** → **毎日note記事を自動投稿** → **Run workflow** で手動実行も可能。
その際 **mode** を `draft` にすると、公開せず下書き保存だけで止められます。

#### ローカルPC（Windows タスクスケジューラ）

```cmd
C:\path\to\python note_auto_poster.py
```

をタスクスケジューラに登録。

### 投稿記事の内容

**1日1銘柄の解説記事**を投稿します。

- **テーマ**: 個別銘柄の解説（日本株・米国株）
- **銘柄**: `note_auto_poster.py` の `STOCKS` に定義。日付でローテーションし、毎日違う銘柄になる（現在22銘柄で一巡）
- **構成**（見出しは固定）
  1. 結論から言うと（無料）
  2. そもそも、どんな会社なのか（無料）
  3. 数字で見る、いまの実力 ← ここから有料300円
  4. 株価は今、高いのか安いのか
  5. 強気に見るなら、ここが理由
  6. 逆に、ここが怖い
  7. 自分ならどう向き合うか
  8. まとめ／参照した情報源／免責事項
- **文体**: 一人称「自分」のですます調。数字を出したら必ず「つまりどういうことか」を添える

#### 体験談は書かせない

読みやすさのために一人称で書きますが、**実際には存在しない売買記録（「2023年5月に買った」「13万円損した」など）は書かせません**。
存在しない体験を有料記事で売ると読者を欺くことになるためです。
一人称で書くのは「考え方・見方・注目点」までに限定しています。

#### 数値はweb検索で裏付ける

株価や業績は日々変わるため、AIの知識だけで書くと古い数値や存在しない数値を「現在の株価」として書いてしまいます。
これを避けるため、Claude APIの**web検索ツール**で実際のデータを取得してから記事を書かせています。

- 検索で確認できなかった項目は埋めず、その旨を明記する
- 数値には基準日を添える
- 記事末尾に参照元のURLを列挙する
- 記事末尾に「投資判断はご自身の責任で」という免責事項を入れる

銘柄を追加・変更したい場合は `note_auto_poster.py` の `STOCKS` リストを編集してください。
販売価格を変えたい場合は同ファイルの `ARTICLE_PRICE` を編集してください（noteの最低価格は100円）。

### ログ・履歴

- `note_poster.log` — 投稿実行ログ
- `posted_articles.jsonl` — 投稿履歴（JSON Lines形式）
