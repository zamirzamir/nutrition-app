const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_ANON_KEY;

module.exports = async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Cache-Control", "public, max-age=3600");
  try {
    const r = await fetch(
      `${SUPABASE_URL}/rest/v1/ingredients?select=id,name,category,calories,protein,fat,carbs,fiber&order=name`,
      { headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` } }
    );
    const data = await r.json();
    if (!r.ok) throw new Error(JSON.stringify(data));
    res.status(200).json(data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};
