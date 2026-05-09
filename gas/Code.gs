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
