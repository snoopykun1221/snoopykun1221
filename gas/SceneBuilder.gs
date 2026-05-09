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
