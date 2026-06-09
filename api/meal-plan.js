const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_ANON_KEY;

module.exports = async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");

  if (req.method === "OPTIONS") return res.status(200).end();
  if (req.method !== "POST") return res.status(405).send("Method Not Allowed");

  try {
    const excluded = Array.isArray(req.body?.excluded) ? req.body.excluded : [];

    const r = await fetch(`${SUPABASE_URL}/rest/v1/rpc/get_meal_plan`, {
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

    const data = await r.json();
    if (!r.ok) throw new Error(JSON.stringify(data));

    const byType = { breakfast: [], lunch: [], dinner: [], snack: [] };
    for (const recipe of data) {
      for (const mt of recipe.meal_type) {
        if (byType[mt]) byType[mt].push(recipe);
      }
    }

    const days = Array.from({ length: 28 }, (_, d) => {
      const breakfast = byType.breakfast[d] || null;
      const lunch     = byType.lunch[d]     || null;
      const dinner    = byType.dinner[d]    || null;
      const snack     = byType.snack[d]     || null;
      const total = [breakfast, lunch, dinner, snack]
        .filter(Boolean)
        .reduce((sum, r) => sum + (r.calories_per_serving || 0), 0);
      return { day: d + 1, breakfast, lunch, dinner, snack, total_calories: Math.round(total) };
    });

    res.status(200).json({ days });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};
