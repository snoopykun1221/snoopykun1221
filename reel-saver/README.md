# リール保存 (Reel Saver)

Instagram のリール・投稿・IGTV を **URL を貼るだけ**で動画/画像として保存できるWebサイト。

![screen](https://placeholder) <!-- 起動後 http://localhost:3000 -->

## 特徴

- リール (`/reel/`) / 投稿 (`/p/`) / IGTV (`/tv/`) に対応
- 複数枚投稿（カルーセル）も個別に保存可能
- サムネイル・キャプションのプレビュー表示
- CORS 制約を回避するためサーバー経由でダウンロードを仲介
- 取得先は Instagram の CDN に限定（オープンプロキシ化を防止）

## セットアップ

Node.js 18 以上が必要です。

```bash
cd reel-saver
npm install
npm start
```

ブラウザで <http://localhost:3000> を開き、URL を貼って「保存」を押すだけ。

ポートを変えたい場合:

```bash
PORT=8080 npm start
```

## ネット上に公開する（無料デプロイ）

誰でもブラウザからアクセスできる状態にするには、Node.js が動く無料ホスティングにデプロイします。**Render が一番簡単**です。

### 方法A: Render（推奨・数分で公開）

1. <https://render.com> に GitHub アカウントで登録
2. ダッシュボードで **New +** → **Blueprint** を選択
3. このリポジトリ (`snoopykun1221/snoopykun1221`) を選ぶ
4. リポジトリ内の `reel-saver/render.yaml` が自動で読み込まれる → **Apply**
5. 数分でビルドが終わり、`https://reel-saver-xxxx.onrender.com` のような公開URLが発行される 🎉

> 無料プランは一定時間アクセスがないとスリープし、次のアクセス時に復帰まで数十秒かかります。

### 方法B: Railway

1. <https://railway.app> に登録 → **New Project** → **Deploy from GitHub repo**
2. Root Directory を `reel-saver` に設定
3. 自動で `npm install` → `npm start` が実行され公開URLが発行される
   （`Dockerfile` があるため Docker ビルドでもOK）

### 方法C: Docker（Fly.io / Cloud Run / VPS など）

```bash
cd reel-saver
docker build -t reel-saver .
docker run -p 3000:3000 reel-saver
```

## 構成

| ファイル | 役割 |
|----------|------|
| `server.js` | Express サーバー。`/api/info`（情報取得）と `/api/download`（ダウンロード仲介） |
| `instagram.js` | URL 解析とメディアURLの取得ロジック |
| `public/index.html` | フロントエンド（UI） |

## 取得の仕組み

1. URL から shortcode を抽出
2. shortcode を数値のメディアIDへ変換し、Instagram の web API (`media/{id}/info`) から取得
3. 失敗した場合は投稿ページの HTML から `og:video` / `og:image` を取得（フォールバック）

## 注意事項

- **公開アカウント**の投稿のみ取得できます（非公開・削除済みは不可）。
- Instagram はスクレイピング対策を頻繁に更新するため、取得ロジックが**将来動かなくなる可能性**があります。
- 取得したコンテンツの著作権は各投稿者に帰属します。無断転載・再配布は Instagram 利用規約や著作権法に触れる場合があります。**私的利用の範囲**でご利用ください。
