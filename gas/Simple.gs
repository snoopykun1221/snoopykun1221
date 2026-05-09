// ====================================================
// 白猫シェフTikTok - シンプル版（1ファイル完結）
// APIキーをここに貼り付けてください↓
// ====================================================
var API_KEY = 'YOUR_API_KEY_HERE';

// ====================================================
// ★ここを実行してください★ テスト（オムライス）
// ====================================================
function testOmurice() { run('オムライス'); }
function testCurry()   { run('カレーライス'); }
function testPasta()   { run('ナポリタン'); }

// ====================================================
// メイン処理
// ====================================================
function run(dish) {
  Logger.log('🐱 ' + dish + ' の動画制作開始！');

  var key = (API_KEY && API_KEY !== 'YOUR_API_KEY_HERE')
    ? API_KEY
    : PropertiesService.getScriptProperties().getProperty('OPENAI_API_KEY');

  if (!key) {
    Logger.log('❌ APIキーが設定されていません！5行目に入力してください');
    return;
  }

  // ① レシピ取得
  Logger.log('📝 レシピ生成中...');
  var recipe = getRecipe(dish, key);
  Logger.log('レシピ取得OK: ' + recipe.steps.length + 'ステップ');

  // ② シーン組み立て
  var scenes = buildScenes(recipe);
  Logger.log('🎬 シーン数: ' + scenes.length);

  // ③ Google Driveフォルダ作成
  var folder = makeFolder('白猫シェフTikTok/' + dish);

  // ④ 画像生成（DALL-E 3）
  Logger.log('🖼️ 画像生成中（' + scenes.length + '枚）...');
  var imageUrls = generateImages(scenes, folder, key);

  // ⑤ 台本ファイル作成
  var docUrl = saveScript(dish, recipe, scenes, folder);

  Logger.log('');
  Logger.log('✅ 完成！');
  Logger.log('📁 フォルダ: https://drive.google.com/drive/folders/' + folder.getId());
  Logger.log('📄 台本: ' + docUrl);
  Logger.log('🖼️ 画像: ' + imageUrls.length + '枚 生成');
}

// ====================================================
// レシピ生成（OpenAI GPT-4o）
// ====================================================
function getRecipe(dish, key) {
  var prompt = '「' + dish + '」のレシピをJSONで返して。\n'
    + '形式: {"name":"","description":"","ingredients":[{"name":"","amount":""}],'
    + '"steps":[{"action":"","description":"","tool":"","duration":5}]}\n'
    + 'stepsは最大10個、各5秒以内のアクション、日本語で。';

  var res = callGPT(prompt, key);
  return JSON.parse(res);
}

// ====================================================
// シーン組み立て
// ====================================================
function buildScenes(recipe) {
  var nya = [0, 3, 6, 9];
  var scenes = [];

  scenes.push({
    index: 0, type: 'opening',
    title: recipe.name,
    narration: 'にゃ〜！今日は「' + recipe.name + '」の作り方を教えるにゃ！',
    cookingAction: 'cute white cat waving hello in kitchen, excited and happy',
    hasNya: true, duration: 5
  });

  var ings = recipe.ingredients.map(function(i){ return i.name; }).join('・');
  scenes.push({
    index: 1, type: 'ingredients',
    title: '材料', narration: '材料はね、' + ings + ' だにゃ！',
    cookingAction: 'cat presenting ingredients on kitchen counter, pointing with paw',
    hasNya: false, duration: 5
  });

  recipe.steps.slice(0, 9).forEach(function(step, i) {
    var idx = scenes.length;
    scenes.push({
      index: idx, type: 'cooking',
      title: step.action,
      narration: step.description + (nya.indexOf(idx) >= 0 ? ' にゃ〜！' : ''),
      cookingAction: step.action + ' ' + (step.tool || ''),
      hasNya: nya.indexOf(idx) >= 0,
      duration: Math.min(step.duration || 5, 5)
    });
  });

  scenes.push({
    index: scenes.length, type: 'ending',
    title: '完成！',
    narration: '完成にゃ〜！美味しく食べてにゃ！チャンネル登録もよろしくにゃ！',
    cookingAction: 'cat proudly presenting finished dish with sparkles, happy face',
    hasNya: true, duration: 5
  });

  return scenes.slice(0, 12);
}

// ====================================================
// DALL-E 3 画像生成
// ====================================================
function generateImages(scenes, folder, key) {
  var style = [
    'cute chibi white cat wearing pink pastel apron',
    'kawaii anime art style, big sparkling eyes',
    'fluffy white fur, not realistic, cartoon illustration',
    'soft pastel color palette, 2D flat illustration',
    'vertical 9:16 composition'
  ].join(', ');

  var urls = [];
  scenes.forEach(function(scene, i) {
    try {
      var prompt = style + ', ' + scene.cookingAction
        + ', bright cheerful kitchen background, high quality digital art';

      var payload = {
        model: 'dall-e-3', prompt: prompt,
        n: 1, size: '1024x1792', quality: 'standard', style: 'vivid'
      };

      var r = UrlFetchApp.fetch('https://api.openai.com/v1/images/generations', {
        method: 'POST',
        headers: { Authorization: 'Bearer ' + key, 'Content-Type': 'application/json' },
        payload: JSON.stringify(payload),
        muteHttpExceptions: true
      });

      var data = JSON.parse(r.getContentText());
      if (data.data && data.data[0]) {
        var url = data.data[0].url;
        var blob = UrlFetchApp.fetch(url).getBlob();
        var name = 'scene' + (i + 1) + '_' + scene.title.replace(/[^\w]/g, '') + '.png';
        folder.createFile(blob.setName(name));
        urls.push(url);
        Logger.log('  ✅ ' + (i+1) + '/' + scenes.length + ': ' + scene.title);
      }
    } catch(e) {
      Logger.log('  ⚠️ シーン' + (i+1) + ' エラー: ' + e.message);
    }
    Utilities.sleep(1200);
  });
  return urls;
}

// ====================================================
// 台本をGoogleドキュメントに保存
// ====================================================
function saveScript(dish, recipe, scenes, folder) {
  var doc = DocumentApp.create('【白猫シェフ】' + dish + ' 台本');
  var b = doc.getBody();

  b.appendParagraph('🐱 白猫シェフ：' + dish).setHeading(DocumentApp.ParagraphHeading.HEADING1);
  b.appendParagraph('作成: ' + new Date().toLocaleString('ja-JP'));
  b.appendParagraph('');

  b.appendParagraph('材料').setHeading(DocumentApp.ParagraphHeading.HEADING2);
  recipe.ingredients.forEach(function(i) {
    b.appendListItem(i.name + ': ' + i.amount);
  });
  b.appendParagraph('');

  b.appendParagraph('シーン構成').setHeading(DocumentApp.ParagraphHeading.HEADING2);
  var total = 0;
  scenes.forEach(function(s) {
    b.appendParagraph('【シーン' + (s.index+1) + '】' + s.title + ' (' + s.duration + '秒)')
     .setHeading(DocumentApp.ParagraphHeading.HEADING3);
    b.appendParagraph('ナレーション: ' + s.narration);
    if (s.hasNya) b.appendParagraph('🐱 ← ここで にゃ〜 SE を挿入！');
    b.appendParagraph('');
    total += s.duration;
  });

  b.appendParagraph('合計: 約' + total + '秒').setBold(true);
  b.appendParagraph('');
  b.appendParagraph('音声ツール推奨').setHeading(DocumentApp.ParagraphHeading.HEADING2);
  b.appendListItem('VOICEVOX（無料・日本語）');
  b.appendListItem('CoeFont（無料プランあり）');
  b.appendListItem('猫SE: 効果音ラボ https://soundeffect-lab.info/');
  b.appendParagraph('');
  b.appendParagraph('動画編集推奨').setHeading(DocumentApp.ParagraphHeading.HEADING2);
  b.appendListItem('CapCut（無料・スマホOK）← おすすめ！');
  b.appendListItem('形式: 縦型 1080×1920 / 30fps');

  doc.saveAndClose();
  moveFileToFolder(doc.getId(), folder);
  return 'https://docs.google.com/document/d/' + doc.getId() + '/edit';
}

// ====================================================
// ユーティリティ
// ====================================================
function callGPT(prompt, key) {
  var r = UrlFetchApp.fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: { Authorization: 'Bearer ' + key, 'Content-Type': 'application/json' },
    payload: JSON.stringify({
      model: 'gpt-4o',
      messages: [{ role: 'user', content: prompt }],
      response_format: { type: 'json_object' }
    }),
    muteHttpExceptions: true
  });
  var d = JSON.parse(r.getContentText());
  if (!d.choices) throw new Error(r.getContentText());
  return d.choices[0].message.content;
}

function makeFolder(path) {
  var parts = path.split('/');
  var f = DriveApp.getRootFolder();
  parts.forEach(function(p) {
    var it = f.getFoldersByName(p);
    f = it.hasNext() ? it.next() : f.createFolder(p);
  });
  return f;
}

function moveFileToFolder(fileId, folder) {
  var file = DriveApp.getFileById(fileId);
  folder.addFile(file);
  DriveApp.getRootFolder().removeFile(file);
}
