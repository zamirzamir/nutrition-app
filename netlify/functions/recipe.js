const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_ANON_KEY;

exports.handler = async (event) => {
  const id = event.queryStringParameters?.id;
  if (!id) return { statusCode: 400, body: JSON.stringify({ error: "id обязателен" }) };

  try {
    const headers = { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` };

    const [rRes, iRes] = await Promise.all([
      fetch(`${SUPABASE_URL}/rest/v1/recipes?id=eq.${encodeURIComponent(id)}&limit=1`, { headers }),
      fetch(`${SUPABASE_URL}/rest/v1/recipe_ingredients?recipe_id=eq.${encodeURIComponent(id)}&select=amount_g,ingredients(id,name,category,calories,protein,fat,carbs,fiber)`, { headers }),
    ]);

    const [recipes, ings] = await Promise.all([rRes.json(), iRes.json()]);
    if (!recipes[0]) return { statusCode: 404, body: JSON.stringify({ error: "Рецепт не найден" }) };

    const recipe = recipes[0];
    const servings = recipe.base_servings || 1;
    let totalCal = 0, totalProt = 0, totalFat = 0, totalCarb = 0, totalFiber = 0;

    const ingredients = ings.map(({ amount_g, ingredients: ing }) => {
      const f = amount_g / 100;
      const cal = (ing.calories || 0) * f;
      const prot = (ing.protein || 0) * f;
      const fat = (ing.fat || 0) * f;
      const carb = (ing.carbs || 0) * f;
      const fiber = (ing.fiber || 0) * f;
      totalCal += cal; totalProt += prot; totalFat += fat; totalCarb += carb; totalFiber += fiber;
      return { id: ing.id, name: ing.name, amount_g,
        calories: Math.round(cal * 10) / 10, protein: Math.round(prot * 10) / 10,
        fat: Math.round(fat * 10) / 10, carbs: Math.round(carb * 10) / 10 };
    });

    return {
      statusCode: 200,
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Cache-Control": "public, max-age=86400",
      },
      body: JSON.stringify({
        ...recipe, ingredients,
        nutrition_per_serving: {
          calories: Math.round(totalCal / servings * 10) / 10,
          protein: Math.round(totalProt / servings * 10) / 10,
          fat: Math.round(totalFat / servings * 10) / 10,
          carbs: Math.round(totalCarb / servings * 10) / 10,
          fiber: Math.round(totalFiber / servings * 10) / 10,
        },
      }),
    };
  } catch (err) {
    return { statusCode: 500, body: JSON.stringify({ error: err.message }) };
  }
};
