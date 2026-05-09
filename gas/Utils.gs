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
