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
