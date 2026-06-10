const OPENAI_KEY = process.env.OPENAI_API_KEY;

module.exports = async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");

  if (req.method === "OPTIONS") return res.status(200).end();
  if (req.method !== "POST") return res.status(405).send("Method Not Allowed");

  const { message, context } = req.body || {};
  if (!message) return res.status(400).json({ error: "message required" });

  if (!OPENAI_KEY) {
    return res.status(500).json({ error: "OpenAI API key not configured" });
  }

  const systemPrompt = `Ты — умный помощник по питанию и здоровью в приложении "Калькулятор КБЖУ".
Помогаешь пользователям с вопросами о еде, рецептах, питании, диетах, калориях, КБЖУ (белки, жиры, углеводы).
Отвечай кратко, по-русски, тёплым тоном. Только на темы питания, здоровья, рецептов, диет и КБЖУ.
Если вопрос совершенно не связан с едой или питанием — вежливо откажи одним предложением.
${context ? "Данные пользователя: " + context : ""}`;

  try {
    const r = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${OPENAI_KEY}`,
      },
      body: JSON.stringify({
        model: "gpt-4o-mini",
        max_tokens: 350,
        temperature: 0.7,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: message },
        ],
      }),
    });

    const data = await r.json();
    if (!r.ok) throw new Error(data.error?.message || "OpenAI error " + r.status);

    const reply = data.choices?.[0]?.message?.content || "";
    res.status(200).json({ reply, message: reply });
  } catch (err) {
    console.error("Chat error:", err.message);
    res.status(500).json({ error: err.message, reply: "Не удалось получить ответ. Попробуйте позже." });
  }
};
