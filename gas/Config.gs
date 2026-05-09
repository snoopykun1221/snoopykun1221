// ============================================================
// Config.gs - 設定ファイル
// ============================================================

const CONFIG = {
  // OpenAI API
  OPENAI_API_KEY: PropertiesService.getScriptProperties().getProperty('OPENAI_API_KEY'),
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
