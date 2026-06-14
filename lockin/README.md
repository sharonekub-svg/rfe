# LockIn — AI study coach (MVP v1)

Tell it your goal + deadline, and Claude builds you a personal day-by-day study plan.
This is the smallest version that proves people want it: **no login, no payment** — just
the core "wow, I'd use this" moment.

## Run it locally

1. Install dependencies:
   ```bash
   npm install
   ```
2. Add your Claude API key:
   ```bash
   cp .env.example .env.local
   # then open .env.local and paste your key from https://console.anthropic.com
   ```
3. Start it:
   ```bash
   npm run dev
   ```
4. Open http://localhost:3000

## Put it online (free) on Vercel

1. Push this repo to GitHub (already done if you're reading this on GitHub).
2. Go to vercel.com → "New Project" → import this repo.
3. Set the **Root Directory** to `lockin`.
4. Add an Environment Variable: `ANTHROPIC_API_KEY` = your key.
5. Deploy. You'll get a live link to share.

## What it does (the brain)

`app/api/plan/route.ts` sends the student's goal/deadline/obstacles to Claude with a
coaching prompt and returns a personal plan. `app/page.tsx` is the form + result screen.

## Next steps (only after real students say "I'd use this")

- **v2:** Supabase accounts → save plans, daily check-ins, streaks.
- **v3:** Stripe → Pro subscription (~$6.99/mo) for unlimited plans + exam-crunch mode.

## Tech

Next.js (App Router) · Claude API · deploy on Vercel. Supabase + Stripe come later.
