import express from "express";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { resolveMedia, extractShortcode } from "./instagram.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

// メディア情報（サムネイル・ダウンロードURL）を返す
app.post("/api/info", async (req, res) => {
  const { url } = req.body || {};
  try {
    const info = await resolveMedia(url);
    res.json({ ok: true, ...info });
  } catch (err) {
    const status = err.code === "INVALID_URL" ? 400 : 404;
    res.status(status).json({ ok: false, error: err.message });
  }
});

// メディアを取得して「保存」させる（CORS回避のためサーバ経由でストリーム）
app.get("/api/download", async (req, res) => {
  const mediaUrl = req.query.url;
  const shortcode = (req.query.name || "reel").replace(/[^A-Za-z0-9_-]/g, "");
  const type = req.query.type === "image" ? "image" : "video";

  if (!mediaUrl || typeof mediaUrl !== "string") {
    return res.status(400).send("url パラメータが必要です");
  }
  // 取得先を Instagram の CDN に限定（オープンプロキシ化を防ぐ）
  let host;
  try {
    host = new URL(mediaUrl).hostname;
  } catch {
    return res.status(400).send("不正なURLです");
  }
  if (!/(cdninstagram\.com|fbcdn\.net)$/.test(host)) {
    return res.status(400).send("許可されていない取得先です");
  }

  try {
    const upstream = await fetch(mediaUrl, {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
          "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
      },
    });
    if (!upstream.ok || !upstream.body) {
      return res.status(502).send("メディアの取得に失敗しました");
    }
    const ext = type === "image" ? "jpg" : "mp4";
    const contentType =
      upstream.headers.get("content-type") ||
      (type === "image" ? "image/jpeg" : "video/mp4");

    res.setHeader("Content-Type", contentType);
    res.setHeader(
      "Content-Disposition",
      `attachment; filename="${shortcode}.${ext}"`
    );
    const len = upstream.headers.get("content-length");
    if (len) res.setHeader("Content-Length", len);

    // Web Streams → Node Stream
    const reader = upstream.body.getReader();
    const pump = async () => {
      const { done, value } = await reader.read();
      if (done) return res.end();
      res.write(Buffer.from(value));
      return pump();
    };
    await pump();
  } catch (err) {
    if (!res.headersSent) res.status(500).send("ダウンロード中にエラーが発生しました");
    else res.end();
  }
});

app.get("/api/health", (_req, res) => res.json({ ok: true }));

app.listen(PORT, () => {
  console.log(`Reel Saver running on http://localhost:${PORT}`);
});
