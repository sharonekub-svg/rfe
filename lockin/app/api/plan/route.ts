import Anthropic from "@anthropic-ai/sdk";

export const runtime = "nodejs";

export async function POST(req: Request) {
  const key = process.env.ANTHROPIC_API_KEY;
  if (!key) {
    return Response.json(
      {
        error:
          "No ANTHROPIC_API_KEY set yet. Copy .env.example to .env.local and add your key from console.anthropic.com.",
      },
      { status: 500 }
    );
  }

  let body: { goal?: string; deadline?: string; time?: string };
  try {
    body = await req.json();
  } catch {
    return Response.json({ error: "Bad request." }, { status: 400 });
  }

  const goal = (body.goal || "").trim();
  const deadline = (body.deadline || "").trim();
  const time = (body.time || "").trim();

  if (!goal) {
    return Response.json({ error: "Goal is required." }, { status: 400 });
  }

  const anthropic = new Anthropic({ apiKey: key });

  const prompt = `You are LockIn, a warm but no-nonsense study coach for students aged 15-25.
A student just told you:
- Goal: ${goal}
- Deadline: ${deadline || "(not specified)"}
- Time available / obstacles: ${time || "(not specified)"}

Build them a clear, motivating, personal study plan. Rules:
- Talk directly to them ("you"), like a coach who's on their side.
- Break the time until the deadline into a realistic day-by-day or week-by-week plan with specific, small, doable tasks. Never vague.
- Assume they procrastinate. Make the first step almost embarrassingly easy so they actually start.
- Include one short "how to beat procrastination today" tip tailored to what they said.
- Keep it under ~350 words. Use simple headers and short bullet points. No fluff, no lecturing.`;

  try {
    const msg = await anthropic.messages.create({
      model: "claude-opus-4-8",
      max_tokens: 1200,
      messages: [{ role: "user", content: prompt }],
    });

    const plan = msg.content
      .filter((b): b is Anthropic.TextBlock => b.type === "text")
      .map((b) => b.text)
      .join("\n")
      .trim();

    return Response.json({ plan });
  } catch (e: unknown) {
    const detail = e instanceof Error ? e.message : "Unknown error";
    return Response.json(
      { error: `The AI coach hit a snag: ${detail}` },
      { status: 502 }
    );
  }
}
