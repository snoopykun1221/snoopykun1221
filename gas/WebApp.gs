// ============================================================
// WebApp.gs - Webアプリ（GAS Webアプリとして公開する場合）
// ============================================================

function doGet() {
  return HtmlService
    .createHtmlOutput(getWebHtml())
    .setTitle('🐱 白猫シェフ TikTok動画クリエイター')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function doPost(e) {
  const dishName = (e && e.parameter && e.parameter.dish) ? e.parameter.dish : 'オムライス';
  try {
    const result = createCatCookingVideo(dishName);
    return ContentService
      .createTextOutput(JSON.stringify({ success: true, data: result, dish: dishName }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ success: false, error: err.message }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

/** Webアプリ内部から呼ぶ GAS サーバー関数 */
function runFromWeb(dishName) {
  return createCatCookingVideo(dishName || 'オムライス');
}

function getWebHtml() {
  return '<!DOCTYPE html>\n' +
'<html lang="ja">\n' +
'<head>\n' +
'  <meta charset="UTF-8">\n' +
'  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n' +
'  <title>🐱 白猫シェフ TikTok動画クリエイター</title>\n' +
'  <style>\n' +
'    * { box-sizing: border-box; margin: 0; padding: 0; }\n' +
'    body {\n' +
'      font-family: "Helvetica Neue", "Hiragino Kaku Gothic Pro", sans-serif;\n' +
'      background: linear-gradient(135deg, #FFE4E1 0%, #FFF0F5 50%, #E8F5E9 100%);\n' +
'      min-height: 100vh;\n' +
'      display: flex;\n' +
'      align-items: center;\n' +
'      justify-content: center;\n' +
'      padding: 20px;\n' +
'    }\n' +
'    .card {\n' +
'      background: white;\n' +
'      border-radius: 24px;\n' +
'      padding: 40px 36px;\n' +
'      box-shadow: 0 12px 48px rgba(255,105,180,0.18);\n' +
'      max-width: 520px;\n' +
'      width: 100%;\n' +
'      text-align: center;\n' +
'    }\n' +
'    .emoji-hero { font-size: 64px; margin-bottom: 8px; }\n' +
'    h1 { color: #FF69B4; font-size: 1.7em; margin-bottom: 6px; }\n' +
'    .subtitle { color: #999; font-size: 0.9em; margin-bottom: 28px; line-height: 1.5; }\n' +
'    .presets { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; margin-bottom: 20px; }\n' +
'    .preset {\n' +
'      background: #FFF0F5;\n' +
'      color: #FF69B4;\n' +
'      border: 1.5px solid #FFB6C1;\n' +
'      padding: 7px 16px;\n' +
'      border-radius: 20px;\n' +
'      cursor: pointer;\n' +
'      font-size: 14px;\n' +
'      transition: all 0.2s;\n' +
'    }\n' +
'    .preset:hover { background: #FF69B4; color: white; }\n' +
'    .input-row { display: flex; gap: 10px; margin-bottom: 18px; }\n' +
'    input {\n' +
'      flex: 1;\n' +
'      padding: 14px 16px;\n' +
'      border: 2px solid #FFB6C1;\n' +
'      border-radius: 12px;\n' +
'      font-size: 16px;\n' +
'      outline: none;\n' +
'      transition: border 0.2s;\n' +
'    }\n' +
'    input:focus { border-color: #FF69B4; }\n' +
'    .btn-create {\n' +
'      background: linear-gradient(135deg, #FF69B4, #FF1493);\n' +
'      color: white;\n' +
'      border: none;\n' +
'      padding: 14px 24px;\n' +
'      border-radius: 12px;\n' +
'      font-size: 15px;\n' +
'      cursor: pointer;\n' +
'      white-space: nowrap;\n' +
'      transition: transform 0.2s, box-shadow 0.2s;\n' +
'    }\n' +
'    .btn-create:hover { transform: scale(1.04); box-shadow: 0 4px 16px rgba(255,20,147,0.3); }\n' +
'    .btn-create:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }\n' +
'    .status {\n' +
'      margin-top: 20px;\n' +
'      padding: 18px;\n' +
'      border-radius: 14px;\n' +
'      font-size: 14px;\n' +
'      line-height: 1.7;\n' +
'      display: none;\n' +
'      text-align: left;\n' +
'    }\n' +
'    .status.loading { background: #FFF9C4; color: #856404; display: block; }\n' +
'    .status.success { background: #E8F5E9; color: #2E7D32; display: block; }\n' +
'    .status.error   { background: #FFEBEE; color: #C62828; display: block; }\n' +
'    .result-links { margin-top: 12px; }\n' +
'    .result-links a {\n' +
'      display: inline-block;\n' +
'      margin: 4px 4px;\n' +
'      padding: 8px 16px;\n' +
'      background: #FF69B4;\n' +
'      color: white;\n' +
'      border-radius: 8px;\n' +
'      text-decoration: none;\n' +
'      font-size: 13px;\n' +
'      transition: background 0.2s;\n' +
'    }\n' +
'    .result-links a:hover { background: #FF1493; }\n' +
'    .steps { margin-top: 16px; font-size: 13px; color: #666; text-align: left; }\n' +
'    .steps li { margin: 4px 0; }\n' +
'  </style>\n' +
'</head>\n' +
'<body>\n' +
'  <div class="card">\n' +
'    <div class="emoji-hero">🐱</div>\n' +
'    <h1>白猫シェフ</h1>\n' +
'    <p class="subtitle">\n' +
'      TikTok 短編動画クリエイター<br>\n' +
'      料理名を入力すると、白猫シェフの<br>AI動画ストーリーボードを自動生成します！\n' +
'    </p>\n' +
'\n' +
'    <div class="presets">\n' +
'      <button class="preset" onclick="setDish(\'オムライス\')">🍳 オムライス</button>\n' +
'      <button class="preset" onclick="setDish(\'チャーハン\')">🍚 チャーハン</button>\n' +
'      <button class="preset" onclick="setDish(\'カレー\')">🍛 カレー</button>\n' +
'      <button class="preset" onclick="setDish(\'パスタ\')">🍝 パスタ</button>\n' +
'      <button class="preset" onclick="setDish(\'唐揚げ\')">🍗 唐揚げ</button>\n' +
'      <button class="preset" onclick="setDish(\'肉じゃが\')">🥘 肉じゃが</button>\n' +
'    </div>\n' +
'\n' +
'    <div class="input-row">\n' +
'      <input type="text" id="dishInput" placeholder="料理名を入力（例: オムライス）" value="オムライス">\n' +
'      <button class="btn-create" id="createBtn" onclick="createVideo()">🎬 作成</button>\n' +
'    </div>\n' +
'\n' +
'    <ul class="steps">\n' +
'      <li>① GPT-4o でレシピを自動生成</li>\n' +
'      <li>② DALL-E 3 で白猫シェフの画像を生成</li>\n' +
'      <li>③ Google Slides にストーリーボードを作成</li>\n' +
'      <li>④ ナレーション台本（にゃ〜入り）を出力</li>\n' +
'    </ul>\n' +
'\n' +
'    <div class="status" id="statusBox"></div>\n' +
'  </div>\n' +
'\n' +
'  <script>\n' +
'    function setDish(d) {\n' +
'      document.getElementById("dishInput").value = d;\n' +
'    }\n' +
'\n' +
'    function createVideo() {\n' +
'      const dish = document.getElementById("dishInput").value.trim();\n' +
'      if (!dish) { alert("料理名を入力してください"); return; }\n' +
'\n' +
'      const btn = document.getElementById("createBtn");\n' +
'      const box = document.getElementById("statusBox");\n' +
'      btn.disabled = true;\n' +
'      box.className = "status loading";\n' +
'      box.innerHTML = "🐱 にゃ〜！白猫シェフが料理中...<br>（AI画像生成のため 2〜5分かかります）";\n' +
'\n' +
'      google.script.run\n' +
'        .withSuccessHandler(function(res) {\n' +
'          btn.disabled = false;\n' +
'          box.className = "status success";\n' +
'          box.innerHTML =\n' +
'            "✅ 完成にゃ〜！「" + dish + "」の動画素材ができました！<br>" +\n' +
'            \'<div class="result-links">\' +\n' +
'            \'<a href="\' + res.slideUrl + \'" target="_blank">📊 ストーリーボード</a>\' +\n' +
'            \'<a href="\' + res.narrationUrl + \'" target="_blank">📄 ナレーション台本</a>\' +\n' +
'            \'<a href="\' + res.folderUrl + \'" target="_blank">📁 画像フォルダ</a>\' +\n' +
'            "</div>";\n' +
'        })\n' +
'        .withFailureHandler(function(err) {\n' +
'          btn.disabled = false;\n' +
'          box.className = "status error";\n' +
'          box.innerHTML = "❌ エラーが発生しました: " + err.message;\n' +
'        })\n' +
'        .runFromWeb(dish);\n' +
'    }\n' +
'  </script>\n' +
'</body>\n' +
'</html>\n';
}
