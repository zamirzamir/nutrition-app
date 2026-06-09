const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_ANON_KEY;

exports.handler = async (event) => {
  if (event.httpMethod === "OPTIONS") {
    return { statusCode: 200, headers: cors(), body: "" };
  }
  if (event.httpMethod !== "POST") {
    return { statusCode: 405, body: "Method Not Allowed" };
  }
  try {
    const body = JSON.parse(event.body || "{}");
    const excluded = Array.isArray(body.excluded) ? body.excluded : [];

    const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/get_meal_plan`, {
      method: "POST",
      headers: {
        apikey: SUPABASE_KEY,
        Authorization: `Bearer ${SUPABASE_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        p_excluded_ingredients: excluded,
        p_breakfast_count: 28,
        p_lunch_count: 28,
        p_dinner_count: 28,
        p_snack_count: 28,
      }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(JSON.stringify(data));

    const byType = { breakfast: [], lunch: [], dinner: [], snack: [] };
    for (const recipe of data) {
      for (const mt of recipe.meal_type) {
        if (byType[mt]) byType[mt].push(recipe);
      }
    }

    const days = [];
    for (let d = 0; d < 28; d++) {
      const breakfast = byType.breakfast[d] || null;
      const lunch     = byType.lunch[d]     || null;
      const dinner    = byType.dinner[d]    || null;
      const snack     = byType.snack[d]     || null;
      const total = [breakfast, lunch, dinner, snack]
        .filter(Boolean)
        .reduce((sum, r) => sum + (r.calories_per_serving || 0), 0);
      days.push({ day: d + 1, breakfast, lunch, dinner, snack, total_calories: Math.round(total) });
    }

    return {
      statusCode: 200,
      headers: { "Content-Type": "application/json", ...cors() },
      body: JSON.stringify({ days }),
    };
  } catch (err) {
    return { statusCode: 500, headers: cors(), body: JSON.stringify({ error: err.message }) };
  }
};

function cors() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
  };
}
