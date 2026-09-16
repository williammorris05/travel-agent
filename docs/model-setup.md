# Natural-language model setup (L4)

Gemini is the proposed free-tier provider. OpenAI is an optional adapter; neither
is enabled by default. The model integration has automated tests, but a real-model
conversation has not yet passed the L4 gate.

1. Create a key in [Google AI Studio](https://aistudio.google.com/apikey).
   Use a free-tier project without billing for a no-cost test. Verify the selected
   model is available to that project. Never paste the key into chat or source code.
2. Copy `backend/.env.example` to `backend/.env` and edit locally:

```dotenv
TRAVEL_DATA_MODE=fixture
TRAVEL_MODEL_PROVIDER=gemini
TRAVEL_MODEL_NAME=gemini-3.8-flash
TRAVEL_MODEL_MAX_CALLS=10
TRAVEL_GEMINI_API_KEY=your-key-here
```

3. Restart the backend with `scripts/dev-backend.ps1`, then select Check connection
   in the preview. Health exposes `chat_available` but never credentials.
4. Start a new trip and try: “I'm leaving Chicago for two nights, flexible dates,
   one adult, USD 500 for the whole trip including all costs. Dorms are fine.”
   Then “Make it more adventurous, but I need a private room.” Correct dates,
   adjust a slider and send another message. All travel prices remain synthetic.

Do not enable billing to get past a quota failure. Free eligibility and account
limits must be checked in AI Studio; the application cannot infer billing status
from a key. Google states free-tier content may be used to improve its products.
Use synthetic travel details for the evaluation.

One extraction call is allowed per submitted message, with no automatic retry or
model tools, a 25-second HTTP timeout, 30-second workflow timeout, and 1,600 output
tokens. The prompt is bounded to 40,000 characters. Failed requests consume the
local call allowance. The allowance is shared by trips in one process and resets
on restart: it is a development guard, not a durable financial budget. A free-tier
project without billing is the cost boundary. Hosted use needs durable accounting.

Conversation messages are stored in server memory (last 20 messages; last 8 sent
as context). Current preferences are authoritative. Provider requests use
`store=false`; this does not override the provider's separate processing policies.

The model proposes supported field changes with source quotes. Pydantic validates
them, and application code produces clarification questions and candidate-backed
explanations. A quote match is not proof of correct semantic interpretation; live
conversation evaluation remains necessary. No model-written prices or citations
are rendered. Unsupported fields require clarification rather than invented support.

For OpenAI, set provider=openai, select a model supporting structured outputs,
and set `TRAVEL_OPENAI_API_KEY`; arrange a spending boundary before a paid test.

Sources checked September 15, 2026:
[Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing),
[Gemini structured outputs](https://ai.google.dev/gemini-api/docs/structured-output),
[Interactions API](https://ai.google.dev/api/interactions-api),
[OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
