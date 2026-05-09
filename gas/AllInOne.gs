// ============================================================
// Config.gs - 設定ファイル
// ============================================================

// ⚠️⚠️⚠️ ここにOpenAI APIキーを直接貼り付けてください ⚠️⚠️⚠️
// 例: const OPENAI_API_KEY_HARDCODED = 'sk-proj-xxxxxxxx...';
// セキュリティのため、このキーが入ったコードはGitHubにpushしないでください！
const OPENAI_API_KEY_HARDCODED = 'YOUR_API_KEY_HERE';

const CONFIG = {
  // OpenAI API（直書きキー優先、無ければスクリプトプロパティを参照）
  OPENAI_API_KEY: (OPENAI_API_KEY_HARDCODED && OPENAI_API_KEY_HARDCODED !== 'YOUR_API_KEY_HERE')
    ? OPENAI_API_KEY_HARDCODED
    : PropertiesService.getScriptProperties().getProperty('OPENAI_API_KEY'),
  OPENAI_CHAT_ENDPOINT: 'https://api.openai.com/v1/chat/completions',
  OPENAI_IMAGE_ENDPOINT: 'https://api.openai.com/v1/images/generations',

  // 動画設定
  MAX_SCENES: 12,        // 最大シーン数（12 × 5秒 = 60秒以内）
  SCENE_DURATION: 5,     // 各シーン最大秒数
  VIDEO_FORMAT: '9:16',  // TikTok縦型フォーマット

  // 白猫シェフのDALL-E画像スタイル
  CAT_BASE_STYLE: [
    'cute chibi white cat wearing a pink pastel apron',
    'kawaii anime art style',
    'big sparkling eyes',
    'fluffy white fur',
    'not realistic, cartoon illustration',
    'soft pastel color palette',
    'clean white background or simple kitchen background',
    'high quality digital art',
    '2D flat illustration'
  ].join(', '),

  // にゃー挿入シーン位置（シーンインデックス）
  NYA_SCENE_INDICES: [0, 3, 6, 9],

  // Google Drive フォルダ名
  ROOT_FOLDER_NAME: '白猫シェフTikTok',

  // 動画仕様
  IMAGE_SIZE: '1024x1792',  // DALL-E 縦型 (9:16)
  IMAGE_QUALITY: 'standard',
  IMAGE_STYLE: 'vivid',
};
// ============================================================
// Utils.gs - ユーティリティ関数
// ============================================================

/**
 * OpenAI API を呼び出す
 */
function callOpenAI(endpoint, payload) {
  if (!CONFIG.OPENAI_API_KEY) {
    throw new Error(
      'OpenAI APIキーが未設定です。\n' +
      'スクリプトエディタ > プロジェクトの設定 > スクリプトプロパティ に\n' +
      'OPENAI_API_KEY を追加してください。'
    );
  }

  const options = {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer ' + CONFIG.OPENAI_API_KEY,
      'Content-Type': 'application/json',
    },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
  };

  const response = UrlFetchApp.fetch(endpoint, options);
  const code = response.getResponseCode();
  const text = response.getContentText();

  if (code !== 200) {
    throw new Error('OpenAI APIエラー (' + code + '): ' + text);
  }

  return JSON.parse(text);
}

/**
 * Google Drive フォルダを取得または作成する（パス対応）
 */
function getOrCreateFolder(path) {
  const parts = path.split('/').filter(p => p.length > 0);
  let folder = DriveApp.getRootFolder();

  parts.forEach(function(part) {
    const iter = folder.getFoldersByName(part);
    folder = iter.hasNext() ? iter.next() : folder.createFolder(part);
  });

  return folder;
}

/**
 * ファイルを指定フォルダに移動（ルートから削除）
 */
function moveFileToFolder(fileId, targetFolder) {
  const file = DriveApp.getFileById(fileId);
  targetFolder.addFile(file);
  DriveApp.getRootFolder().removeFile(file);
  return file;
}

/**
 * 指定ミリ秒スリープ（API制限対策）
 */
function sleep(ms) {
  Utilities.sleep(ms);
}

/**
 * ゼロパディング
 */
function zeroPad(n, digits) {
  return String(n).padStart(digits, '0');
}

/**
 * シーンタイプに対応する背景色
 */
function getSceneColor(type) {
  const colors = {
    opening: '#FFF9C4',
    ingredients: '#E8F5E9',
    cooking: '#E3F2FD',
    ending: '#FCE4EC',
  };
  return colors[type] || '#FFFFFF';
}

/**
 * 日本語のアクション → 英語のDALL-Eプロンプト変換
 */
function translateCookingAction(action) {
  const map = [
    ['卵を割',    'carefully cracking an egg with tiny paws'],
    ['卵をかき混ぜ', 'vigorously whisking eggs in a bowl'],
    ['卵を溶',    'beating eggs with a fork in a bowl'],
    ['ご飯を炒め',  'stir-frying rice in a large frying pan'],
    ['ケチャップ',  'squeezing a ketchup bottle with both paws'],
    ['炒め',     'stirring ingredients in a frying pan'],
    ['切',      'carefully chopping vegetables on a cutting board'],
    ['煮',      'stirring a bubbling pot on the stove'],
    ['盛り付け',   'carefully plating food on a dish'],
    ['包む',     'gently wrapping food'],
    ['焼',      'cooking in a sizzling frying pan'],
    ['混ぜ',     'mixing ingredients in a bowl'],
    ['茹で',     'boiling ingredients in a pot'],
    ['揚げ',     'deep frying in a pot'],
    ['蒸',      'steaming food'],
    ['材料を用意',  'lining up all ingredients on a kitchen counter'],
    ['ボウル',    'using a mixing bowl'],
    ['フライパン',  'using a frying pan'],
    ['完成',     'proudly presenting the finished dish'],
  ];

  for (let i = 0; i < map.length; i++) {
    if (action.indexOf(map[i][0]) !== -1) {
      return map[i][1];
    }
  }

  // デフォルト: アクション名をそのまま使う
  return 'performing a cooking step: ' + action;
}
// ============================================================
// Recipe.gs - レシピ生成 (OpenAI GPT-4o)
// ============================================================

/**
 * 料理名からレシピをAIで生成する
 * @param {string} dishName 料理名（例: オムライス）
 * @returns {Object} recipe オブジェクト
 */
function generateRecipe(dishName) {
  const prompt =
    'あなたはプロの料理研究家です。「' + dishName + '」のシンプルなレシピを作成してください。\n\n' +
    '以下のJSON形式で返してください（日本語）:\n' +
    '{\n' +
    '  "name": "料理名",\n' +
    '  "description": "料理の魅力を伝える一文",\n' +
    '  "servings": "2人前",\n' +
    '  "ingredients": [\n' +
    '    {"name": "材料名", "amount": "量（例: 2個、100g）"}\n' +
    '  ],\n' +
    '  "steps": [\n' +
    '    {\n' +
    '      "stepNumber": 1,\n' +
    '      "action": "アクション名（短く。例: 卵を割る）",\n' +
    '      "narration": "視聴者への説明（1文、やさしい口調）",\n' +
    '      "tool": "使う道具（例: ボウル、フライパン）",\n' +
    '      "duration": 5\n' +
    '    }\n' +
    '  ]\n' +
    '}\n\n' +
    '重要なルール:\n' +
    '- stepsは最大10個（オープニングとエンディングを合わせて12シーン以内）\n' +
    '- 各ステップは5秒以内に表現できる1アクション\n' +
    '- 視覚的でわかりやすいアクション（切る、混ぜる、焼くなど）\n' +
    '- narrationは「〜にゃ！」などかわいい語尾は不要（後で追加します）\n' +
    '- ingredientsは最大8個';

  const result = callOpenAI(CONFIG.OPENAI_CHAT_ENDPOINT, {
    model: 'gpt-4o',
    messages: [{ role: 'user', content: prompt }],
    response_format: { type: 'json_object' },
    temperature: 0.7,
  });

  return JSON.parse(result.choices[0].message.content);
}
// ============================================================
// SceneBuilder.gs - シーン構成の生成
// ============================================================

/**
 * レシピからシーンリストを生成する
 * @param {Object} recipe generateRecipe() の戻り値
 * @returns {Array} scenes 配列
 */
function buildScenes(recipe) {
  const scenes = [];

  // ── オープニング ──────────────────────────────────
  scenes.push({
    index: 0,
    type: 'opening',
    title: recipe.name,
    narration: 'にゃ〜！今日は「' + recipe.name + '」の作り方を教えるにゃ！',
    hasNya: true,
    duration: 5,
    cookingAction: 'standing in kitchen waving hello with excitement',
  });

  // ── 材料紹介 ──────────────────────────────────────
  const ingredientText = recipe.ingredients
    .map(function(i) { return i.name + ' ' + i.amount; })
    .join('、');

  scenes.push({
    index: 1,
    type: 'ingredients',
    title: '材料をそろえよう',
    narration: '材料はこちらにゃ：' + ingredientText,
    hasNya: false,
    duration: 5,
    cookingAction: 'presenting all ingredients laid out on a kitchen counter, pointing with paw',
  });

  // ── 調理ステップ ──────────────────────────────────
  const maxSteps = CONFIG.MAX_SCENES - 3; // -3: opening / ingredients / ending
  const steps = recipe.steps.slice(0, maxSteps);

  steps.forEach(function(step, i) {
    const sceneIndex = i + 2;
    const hasNya = CONFIG.NYA_SCENE_INDICES.indexOf(sceneIndex) !== -1;

    scenes.push({
      index: sceneIndex,
      type: 'cooking',
      stepNumber: step.stepNumber || (i + 1),
      title: step.action,
      narration: step.narration + (hasNya ? '　にゃ〜！' : ''),
      hasNya: hasNya,
      tool: step.tool || '',
      duration: Math.min(step.duration || 5, CONFIG.SCENE_DURATION),
      cookingAction: translateCookingAction(step.action),
    });
  });

  // ── エンディング ──────────────────────────────────
  scenes.push({
    index: scenes.length,
    type: 'ending',
    title: '完成！いただきます！',
    narration: '完成にゃ〜！おいしく食べてにゃ！チャンネル登録もよろしくにゃ！',
    hasNya: true,
    duration: 5,
    cookingAction: 'proudly presenting the finished dish with sparkles around, happy face',
  });

  return scenes;
}

/**
 * シーンの合計秒数を計算する
 */
function calcTotalDuration(scenes) {
  return scenes.reduce(function(sum, s) { return sum + (s.duration || 5); }, 0);
}
// ============================================================
// ImageGenerator.gs - DALL-E 3 で猫の画像を生成してDriveに保存
// ============================================================

/**
 * 全シーンの画像を生成してGoogle Driveに保存する
 * @param {Array} scenes buildScenes() の戻り値
 * @param {Folder} folder 保存先 Drive フォルダ
 * @returns {Array} images 配列 { scene, fileId, fileUrl, driveUrl, error }
 */
function generateAllImages(scenes, folder) {
  const images = [];

  scenes.forEach(function(scene, i) {
    Logger.log('  🖼️ 画像生成 ' + (i + 1) + '/' + scenes.length + ': ' + scene.title);

    const prompt = buildImagePrompt(scene);

    try {
      const result = callOpenAI(CONFIG.OPENAI_IMAGE_ENDPOINT, {
        model: 'dall-e-3',
        prompt: prompt,
        n: 1,
        size: CONFIG.IMAGE_SIZE,
        quality: CONFIG.IMAGE_QUALITY,
        style: CONFIG.IMAGE_STYLE,
      });

      const imageUrl = result.data[0].url;
      const blob = UrlFetchApp.fetch(imageUrl).getBlob();
      const fileName = 'scene_' + zeroPad(i + 1, 2) + '_' + scene.title.replace(/[\/\\:*?"<>|]/g, '') + '.png';
      const file = folder.createFile(blob.setName(fileName));

      images.push({
        scene: scene,
        fileId: file.getId(),
        fileUrl: file.getUrl(),
        driveUrl: 'https://drive.google.com/file/d/' + file.getId() + '/view',
        prompt: prompt,
        error: null,
      });

    } catch (e) {
      Logger.log('  ⚠️ 画像生成エラー: ' + e.message);
      images.push({
        scene: scene,
        fileId: null,
        fileUrl: null,
        driveUrl: null,
        prompt: prompt,
        error: e.message,
      });
    }

    // DALL-E のレート制限対策（1画像あたり1秒待機）
    sleep(1200);
  });

  return images;
}

/**
 * シーン情報から DALL-E プロンプトを生成する
 */
function buildImagePrompt(scene) {
  let actionDesc = scene.cookingAction || 'cooking in a kitchen';
  let bgDesc = 'bright cheerful kitchen background';

  switch (scene.type) {
    case 'opening':
      bgDesc = 'colorful kitchen with TikTok logo style background';
      break;
    case 'ingredients':
      bgDesc = 'clean kitchen counter with ingredients displayed';
      break;
    case 'cooking':
      bgDesc = 'modern kitchen with stove and utensils';
      break;
    case 'ending':
      bgDesc = 'beautiful table setting, celebratory atmosphere, confetti';
      break;
  }

  const parts = [
    CONFIG.CAT_BASE_STYLE,
    actionDesc,
    bgDesc,
    'vertical composition 9:16 ratio',
    'TikTok short video style',
    'no text overlay',
  ];

  return parts.join(', ');
}
// ============================================================
// NarrationScript.gs - ナレーション・音声スクリプト生成
// ============================================================

/**
 * 全シーンのナレーションスクリプトオブジェクトを作成する
 * @param {Array} scenes
 * @returns {Object} { totalDuration, scripts[] }
 */
function buildNarrationScript(scenes) {
  const scripts = scenes.map(function(scene) {
    return {
      sceneNumber: scene.index + 1,
      type: scene.type,
      title: scene.title,
      narration: scene.narration,
      duration: scene.duration,
      hasNya: scene.hasNya,
      soundEffect: scene.hasNya ? '🐱 にゃ〜（猫の鳴き声 SE）' : '',
      ttsNote: buildTtsNote(scene),
    };
  });

  return {
    totalDuration: calcTotalDuration(scenes),
    scripts: scripts,
  };
}

/**
 * TTS（音声合成）用の読み上げテキストを生成する
 * にゃーの鳴き声はSEとして別途挿入する想定
 */
function buildTtsNote(scene) {
  // にゃーを除いたナレーション本文
  const cleanText = scene.narration.replace(/　?にゃ〜！/g, '').replace(/にゃ〜！/g, '');

  let note = '読み上げ: 「' + cleanText + '」';

  if (scene.hasNya) {
    note += '\n→ にゃ〜 SE をナレーションの後に挿入';
  }

  if (scene.type === 'cooking' && scene.tool) {
    note += '\n→ 道具SE候補: ' + scene.tool + ' の音（例: フライパンなら油の音、ボウルなら混ぜる音）';
  }

  return note;
}

/**
 * ナレーションスクリプトをGoogle Documentに書き出す
 * @param {string} dishName
 * @param {Object} narration buildNarrationScript() の戻り値
 * @param {Object} recipe
 * @param {Folder} folder
 * @returns {string} ドキュメントURL
 */
function saveNarrationDoc(dishName, narration, recipe, folder) {
  const doc = DocumentApp.create('【白猫シェフ】' + dishName + '　ナレーション台本');
  const body = doc.getBody();

  // タイトル
  body.appendParagraph('🐱 白猫シェフの料理教室')
      .setHeading(DocumentApp.ParagraphHeading.TITLE);
  body.appendParagraph('料理：' + dishName)
      .setHeading(DocumentApp.ParagraphHeading.SUBTITLE);
  body.appendParagraph('合計時間：約 ' + narration.totalDuration + ' 秒 / ' + narration.scripts.length + ' シーン');
  body.appendParagraph('作成日：' + new Date().toLocaleString('ja-JP'));
  body.appendParagraph('');

  // 材料リスト
  body.appendParagraph('📋 材料').setHeading(DocumentApp.ParagraphHeading.HEADING1);
  recipe.ingredients.forEach(function(ing) {
    body.appendListItem('・' + ing.name + '：' + ing.amount);
  });
  body.appendParagraph('');

  // シーン別台本
  body.appendParagraph('🎬 シーン別ナレーション台本').setHeading(DocumentApp.ParagraphHeading.HEADING1);

  narration.scripts.forEach(function(s) {
    const header = 'シーン ' + s.sceneNumber + '：' + s.title + '（' + s.duration + '秒）';
    body.appendParagraph(header).setHeading(DocumentApp.ParagraphHeading.HEADING2);

    body.appendParagraph('【ナレーション】').setBold(true);
    body.appendParagraph(s.narration);

    if (s.soundEffect) {
      body.appendParagraph('【効果音】' + s.soundEffect);
    }

    body.appendParagraph('【音声メモ】');
    body.appendParagraph(s.ttsNote);
    body.appendParagraph('');
  });

  // 音声制作ガイド
  body.appendParagraph('🎵 音声制作ガイド').setHeading(DocumentApp.ParagraphHeading.HEADING1);

  body.appendParagraph('■ ナレーション（TTS）推奨ツール').setBold(true);
  body.appendListItem('VOICEVOX（無料・日本語）: https://voicevox.hiroshiba.jp/');
  body.appendListItem('CoeFont（無料プランあり）: https://coefont.cloud/');
  body.appendListItem('ElevenLabs（高品質・英語対応）: https://elevenlabs.io/');
  body.appendListItem('にじボイス（日本語・アニメ調）: https://nijivoice.com/');
  body.appendParagraph('');

  body.appendParagraph('■ 猫の鳴き声SE（無料素材）').setBold(true);
  body.appendListItem('Freesound.org → 「cat meow cute」で検索');
  body.appendListItem('効果音ラボ: https://soundeffect-lab.info/ → 動物 > 猫');
  body.appendListItem('Pixabay: https://pixabay.com/sound-effects/search/cat/');
  body.appendParagraph('');

  body.appendParagraph('■ BGM推奨').setBold(true);
  body.appendListItem('YouTube Audio Library → 「cute」「cooking」でフィルタ');
  body.appendListItem('Pixabay Music: https://pixabay.com/music/search/cute/');
  body.appendListItem('DOVA-SYNDROME: https://dova-s.jp/');
  body.appendParagraph('');

  body.appendParagraph('🎬 動画編集ガイド').setHeading(DocumentApp.ParagraphHeading.HEADING1);
  body.appendListItem('推奨ツール: CapCut（無料・スマホ対応）/ DaVinci Resolve / Adobe Premiere Rush');
  body.appendListItem('フォーマット: 縦型 9:16 → 1080×1920px');
  body.appendListItem('フレームレート: 30fps');
  body.appendListItem('各シーン: 最大5秒でカット');
  body.appendListItem('テキスト: 字幕（料理名・手順）を画面下部に追加推奨');
  body.appendListItem('エフェクト: にゃーのとき猫の足跡やハートのアニメーション追加で可愛さUP！');

  doc.saveAndClose();

  moveFileToFolder(doc.getId(), folder);
  return 'https://docs.google.com/document/d/' + doc.getId() + '/edit';
}
// ============================================================
// Storyboard.gs - Google Slides でストーリーボードを作成
// ============================================================

/**
 * Google Slides にストーリーボードを作成する
 * @param {string} dishName
 * @param {Array} scenes
 * @param {Array} images generateAllImages() の戻り値
 * @param {Object} narration buildNarrationScript() の戻り値
 * @param {Folder} folder
 * @returns {string} プレゼンテーションURL
 */
function createStoryboard(dishName, scenes, images, narration, folder) {
  const pres = SlidesApp.create('【白猫シェフ】' + dishName + ' ストーリーボード');

  // ── タイトルスライド ───────────────────────────────
  const titleSlide = pres.getSlides()[0];
  titleSlide.getBackground().setSolidFill('#FFE4E1');
  titleSlide.getPageElements().forEach(function(el) { el.remove(); });

  insertTextBox(titleSlide, '🐱 白猫シェフの料理教室 🐱', 40, 80, 640, 60, 32, true, '#FF69B4');
  insertTextBox(titleSlide, dishName, 40, 160, 640, 80, 48, true, '#FF1493');
  insertTextBox(titleSlide, '全 ' + scenes.length + ' シーン　合計約 ' + narration.totalDuration + ' 秒', 40, 260, 640, 40, 18, false, '#888888');
  insertTextBox(titleSlide, '縦型 9:16　TikTok フォーマット', 40, 310, 640, 30, 14, false, '#AAAAAA');

  // ── シーンごとのスライド ──────────────────────────
  scenes.forEach(function(scene, i) {
    const slide = pres.appendSlide(SlidesApp.PredefinedLayout.BLANK);
    slide.getBackground().setSolidFill(getSceneColor(scene.type));

    // ヘッダー行
    insertTextBox(slide, 'シーン ' + (i + 1) + ' / ' + scenes.length, 10, 5, 250, 25, 12, false, '#888888');
    insertTextBox(slide, '⏱ ' + scene.duration + '秒', 580, 5, 120, 25, 14, true, '#FF4500');

    // タイトル
    insertTextBox(slide, scene.title, 10, 35, 700, 45, 22, true, '#333333');

    // 画像（Drive から挿入）
    const imgData = images[i];
    if (imgData && imgData.fileId) {
      try {
        const blob = DriveApp.getFileById(imgData.fileId).getBlob();
        const img = slide.insertImage(blob);
        img.setLeft(220).setTop(90).setWidth(270).setHeight(210);
      } catch (e) {
        insertTextBox(slide, '🖼️ 画像エラー: ' + e.message, 10, 90, 700, 30, 10, false, '#CC0000');
      }
    } else if (imgData && imgData.error) {
      insertTextBox(slide, '⚠️ 画像生成失敗: ' + imgData.error, 10, 90, 700, 30, 10, false, '#CC0000');
    }

    // ナレーション
    insertTextBox(slide, '🎤 ' + scene.narration, 10, 310, 700, 55, 13, false, '#333333');

    // 効果音ラベル
    if (scene.hasNya) {
      insertTextBox(slide, '🐱 にゃ〜！', 580, 300, 120, 35, 16, true, '#FF69B4');
    }

    if (scene.tool) {
      insertTextBox(slide, '🔧 ' + scene.tool, 10, 370, 300, 25, 12, false, '#555555');
    }

    // シーンタイプバッジ
    const typeLabel = { opening: '🌟 オープニング', ingredients: '📋 材料', cooking: '🍳 調理', ending: '🎉 エンディング' };
    insertTextBox(slide, typeLabel[scene.type] || scene.type, 490, 370, 220, 25, 12, false, '#666666');
  });

  // ── 制作メモスライド ──────────────────────────────
  const memoSlide = pres.appendSlide(SlidesApp.PredefinedLayout.BLANK);
  memoSlide.getBackground().setSolidFill('#F3E5F5');
  insertTextBox(memoSlide, '📝 動画制作メモ', 20, 10, 680, 40, 24, true, '#7B1FA2');
  insertTextBox(memoSlide, [
    '【ナレーション】VOICEVOX / CoeFont / にじボイス',
    '【猫の鳴き声SE】Freesound.org → "cat meow cute"',
    '【BGM】YouTube Audio Library → "cute cooking"',
    '【動画編集】CapCut（スマホ） / DaVinci Resolve（PC）',
    '【フォーマット】縦型 1080×1920px / 30fps / 9:16',
    '【テキスト】字幕（料理名・手順）を画面下部に追加',
    '【エフェクト】にゃーシーンに猫の足跡アニメを追加！',
  ].join('\n'), 20, 60, 680, 310, 14, false, '#333333');

  pres.saveAndClose();

  moveFileToFolder(pres.getId(), folder);
  return 'https://docs.google.com/presentation/d/' + pres.getId() + '/edit';
}

/**
 * スライドにテキストボックスを挿入するヘルパー
 */
function insertTextBox(slide, text, left, top, width, height, fontSize, bold, color) {
  const box = slide.insertTextBox(text, left, top, width, height);
  const style = box.getText().getTextStyle();
  style.setFontSize(fontSize || 14);
  if (bold) style.setBold(true);
  if (color) style.setForegroundColor(color);
  return box;
}
// ============================================================
// Code.gs - メイン処理
// ============================================================

/**
 * 白猫シェフのTikTok動画ストーリーボードを作成するメイン関数
 *
 * @param {string} dishName  料理名（例: 'オムライス'）
 * @returns {Object} { slideUrl, narrationUrl, folderUrl }
 */
function createCatCookingVideo(dishName) {
  dishName = dishName || 'オムライス';

  Logger.log('🐱 ====================================');
  Logger.log('🐱 白猫シェフ TikTok動画作成開始');
  Logger.log('🐱 料理: ' + dishName);
  Logger.log('🐱 ====================================');

  // ① Google Drive フォルダを準備
  const folder = getOrCreateFolder(CONFIG.ROOT_FOLDER_NAME + '/' + dishName);
  Logger.log('📁 フォルダ準備完了: ' + folder.getName());

  // ② レシピをAIで生成
  Logger.log('📝 レシピを生成中...');
  const recipe = generateRecipe(dishName);
  Logger.log('✅ レシピ生成完了 / ステップ数: ' + recipe.steps.length);

  // ③ シーン構成を組み立て
  Logger.log('🎬 シーンを構成中...');
  const scenes = buildScenes(recipe);
  Logger.log('✅ ' + scenes.length + ' シーン / 合計: ' + calcTotalDuration(scenes) + '秒');

  // ④ 各シーンの画像をDALL-E 3で生成
  Logger.log('🖼️ AI画像を生成中（DALL-E 3）...');
  const images = generateAllImages(scenes, folder);
  const successCount = images.filter(function(i) { return !i.error; }).length;
  Logger.log('✅ 画像生成完了: ' + successCount + '/' + images.length);

  // ⑤ ナレーション台本を作成
  Logger.log('🎤 ナレーション台本を作成中...');
  const narration = buildNarrationScript(scenes);
  const narrationUrl = saveNarrationDoc(dishName, narration, recipe, folder);
  Logger.log('✅ ナレーション台本: ' + narrationUrl);

  // ⑥ Google Slides ストーリーボードを作成
  Logger.log('📊 ストーリーボードを作成中...');
  const slideUrl = createStoryboard(dishName, scenes, images, narration, folder);
  Logger.log('✅ ストーリーボード: ' + slideUrl);

  const folderUrl = 'https://drive.google.com/drive/folders/' + folder.getId();

  Logger.log('');
  Logger.log('🎉 ====================================');
  Logger.log('🎉 完成にゃ〜！');
  Logger.log('📊 ストーリーボード: ' + slideUrl);
  Logger.log('📄 ナレーション台本: ' + narrationUrl);
  Logger.log('📁 素材フォルダ:    ' + folderUrl);
  Logger.log('🎉 ====================================');

  return { slideUrl: slideUrl, narrationUrl: narrationUrl, folderUrl: folderUrl };
}

// ── スクリプトエディタから直接テスト実行する関数 ────────────

/** オムライスで動画を作成（テスト用） */
function testOmurice() {
  createCatCookingVideo('オムライス');
}

/** チャーハンで動画を作成（テスト用） */
function testFriedRice() {
  createCatCookingVideo('チャーハン');
}

/** カレーで動画を作成（テスト用） */
function testCurry() {
  createCatCookingVideo('カレー');
}

/** パスタで動画を作成（テスト用） */
function testPasta() {
  createCatCookingVideo('パスタ');
}
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
