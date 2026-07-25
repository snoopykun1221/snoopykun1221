# どこでも動く汎用デプロイ用（Railway / Fly.io / Cloud Run / VPS など）
FROM node:20-alpine

WORKDIR /app

# 依存関係を先にインストール（キャッシュを効かせる）
COPY package.json package-lock.json* ./
RUN npm install --omit=dev

# アプリ本体をコピー
COPY . .

# ホスティング側が渡す PORT を使用（デフォルト3000）
ENV PORT=3000
EXPOSE 3000

CMD ["npm", "start"]
