// Instagram の投稿URLから動画・画像のメディア情報を取得するモジュール。
//
// 注意: Instagram はスクレイピング対策を頻繁に更新するため、
// この取得ロジックは将来動かなくなる可能性があります。
// また、他人の著作物のダウンロード・再配布は Instagram の利用規約や
// 著作権法に抵触する場合があります。私的利用の範囲でご利用ください。

const IG_APP_ID = "936619743392459";
const SHORTCODE_ALPHABET =
  "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";

// リール / 投稿 / IGTV の各URL形式から shortcode を取り出す。
export function extractShortcode(rawUrl) {
  if (!rawUrl || typeof rawUrl !== "string") return null;
  let url;
  try {
    url = new URL(rawUrl.trim());
  } catch {
    return null;
  }
  if (!/(^|\.)instagram\.com$/.test(url.hostname)) return null;

  // /reel/xxxx/  /reels/xxxx/  /p/xxxx/  /tv/xxxx/  /username/reel/xxxx/
  const m = url.pathname.match(/\/(?:reel|reels|p|tv)\/([A-Za-z0-9_-]+)/);
  return m ? m[1] : null;
}

// shortcode から数値のメディアIDへ変換する（base64ライクなデコード）。
function shortcodeToMediaId(shortcode) {
  let id = 0n;
  for (const ch of shortcode) {
    const value = SHORTCODE_ALPHABET.indexOf(ch);
    if (value < 0) return null;
    id = id * 64n + BigInt(value);
  }
  return id.toString();
}

const COMMON_HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
  "Accept-Language": "en-US,en;q=0.9,ja;q=0.8",
};

// 取得したメディア情報を共通フォーマットへ整える。
function normalizeMediaItem(item) {
  const results = [];

  const pushFromNode = (node) => {
    if (node.video_versions && node.video_versions.length) {
      // 一番解像度の高い動画を選ぶ
      const best = [...node.video_versions].sort(
        (a, b) => (b.width || 0) - (a.width || 0)
      )[0];
      results.push({ type: "video", url: best.url });
    } else if (
      node.image_versions2 &&
      node.image_versions2.candidates &&
      node.image_versions2.candidates.length
    ) {
      const best = [...node.image_versions2.candidates].sort(
        (a, b) => (b.width || 0) - (a.width || 0)
      )[0];
      results.push({ type: "image", url: best.url });
    }
  };

  if (item.carousel_media && item.carousel_media.length) {
    for (const child of item.carousel_media) pushFromNode(child);
  } else {
    pushFromNode(item);
  }

  const thumb =
    item.image_versions2?.candidates?.[0]?.url ||
    item.carousel_media?.[0]?.image_versions2?.candidates?.[0]?.url ||
    null;

  return {
    shortcode: item.code || null,
    caption: item.caption?.text || "",
    username: item.user?.username || item.owner?.username || "",
    thumbnail: thumb,
    media: results,
  };
}

// 手法A: 非公開の web API (media/{id}/info) から取得する。
async function fetchViaApi(shortcode) {
  const mediaId = shortcodeToMediaId(shortcode);
  if (!mediaId) return null;

  const endpoint = `https://i.instagram.com/api/v1/media/${mediaId}/info/`;
  const res = await fetch(endpoint, {
    headers: {
      ...COMMON_HEADERS,
      "X-IG-App-ID": IG_APP_ID,
      Referer: `https://www.instagram.com/reel/${shortcode}/`,
    },
  });
  if (!res.ok) return null;
  const data = await res.json();
  const item = data?.items?.[0];
  if (!item) return null;
  return normalizeMediaItem(item);
}

// 手法B: 投稿ページのHTMLから og:video / og:image を拾う（フォールバック）。
async function fetchViaHtml(shortcode) {
  const endpoint = `https://www.instagram.com/reel/${shortcode}/`;
  const res = await fetch(endpoint, { headers: COMMON_HEADERS });
  if (!res.ok) return null;
  const html = await res.text();

  const grab = (prop) => {
    const re = new RegExp(
      `<meta[^>]+property=["']${prop}["'][^>]+content=["']([^"']+)["']`,
      "i"
    );
    const m = html.match(re);
    return m ? decodeHtmlEntities(m[1]) : null;
  };

  const video = grab("og:video") || grab("og:video:secure_url");
  const image = grab("og:image");
  const media = [];
  if (video) media.push({ type: "video", url: video });
  else if (image) media.push({ type: "image", url: image });
  if (!media.length) return null;

  return {
    shortcode,
    caption: grab("og:title") || "",
    username: "",
    thumbnail: image,
    media,
  };
}

function decodeHtmlEntities(str) {
  return str
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#039;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");
}

// URLからメディア情報を解決する。手法Aを優先し、失敗したら手法Bへ。
export async function resolveMedia(rawUrl) {
  const shortcode = extractShortcode(rawUrl);
  if (!shortcode) {
    const err = new Error(
      "Instagram のリール/投稿URLではありません。例: https://www.instagram.com/reel/xxxxxxxxx/"
    );
    err.code = "INVALID_URL";
    throw err;
  }

  let result = null;
  try {
    result = await fetchViaApi(shortcode);
  } catch {
    /* 手法Bへ */
  }
  if (!result || !result.media.length) {
    try {
      result = await fetchViaHtml(shortcode);
    } catch {
      /* noop */
    }
  }

  if (!result || !result.media.length) {
    const err = new Error(
      "メディアを取得できませんでした。非公開アカウント・削除済み・URL誤り、または Instagram 側の仕様変更が原因の可能性があります。"
    );
    err.code = "NOT_FOUND";
    throw err;
  }
  result.shortcode = result.shortcode || shortcode;
  return result;
}
