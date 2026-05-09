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
