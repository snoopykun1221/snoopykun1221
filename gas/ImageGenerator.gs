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
