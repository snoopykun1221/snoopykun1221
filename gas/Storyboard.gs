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
