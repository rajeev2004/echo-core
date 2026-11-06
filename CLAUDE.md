# Voice AI Agent — Project Context

Production-grade voice calling agent built on Pipecat. Read this file in
full before making changes — it's the persistent context for every session.

## Architecture: cascaded pipeline

Transport (SmallWebRTC for local dev, Twilio once going live) →
Deepgram Nova-3 (STT) → LLM (swappable — see below) → Inworld Realtime
TTS-2 Flash (TTS) → back to the transport.

**Standing policy, not just a build step:** all development — the
cascade, the LLM bake-off, and the S2S variant — runs over
`SmallWebRTCTransport`, free and with no account needed. Twilio is only
brought in for production and the final real-call validation pass, not
for day-to-day iteration. Don't reach for Twilio mid-development just
because a task mentions calls or telephony — check whether SmallWebRTC
already covers it first.

A parallel Gemini Live (S2S) variant shares the same transport as the
cascade (SmallWebRTC in dev, Twilio once live), for an A/B comparison.
Keep both buildable from one codebase — swap the reasoning/speech layer
via config, not a rewrite.

## Confirmed services and model IDs

- STT: Deepgram Nova-3 (`DeepgramSTTService`)
- LLM: not fixed — this is itself a benchmarking target, not a settled
  choice. Build an LLM provider abstraction (one interface, swappable
  implementation) so the active model changes via config/env var, never
  via code edits. Candidates to test:
  - Claude Haiku 5.5, model id `claude-haiku-5-5` (`AnthropicLLMService`)
  - GPT-5.4 mini, model id `gpt-5.4-mini` (`OpenAILLMService`)
  - GPT-5.4 nano, model id `gpt-5.4-nano` (`OpenAILLMService`)
  - Gemini 3.x Flash (`GoogleLLMService`) — used *inside the cascade*
    here; a separate test from the Gemini Live S2S branch below
  Start with GPT-5.4 mini since OpenAI credits are available now, but
  don't hardcode assumptions anywhere about which provider is active.
- TTS: Inworld Realtime TTS-2 Flash (`InworldTTSService`)
- Telephony: Twilio Media Streams
- S2S comparison branch: Gemini Live (`GeminiLiveLLMService`)

## Build order — do not skip steps

Build and verify each stage before adding the next. Don't jump straight to
the full pipeline in one commit — isolating one new variable per step
makes failures easy to localize.

1. Scaffold project + `.env` with all keys (Deepgram, OpenAI, Inworld).
   Never hardcode keys, never commit `.env`. Twilio keys aren't needed
   yet — see step 7.
2. Build and run locally over `SmallWebRTCTransport` (Pipecat's default
   dev transport — no account, no ngrok, no telephony). Use the dev
   runner's prebuilt browser client at `localhost:7860/client` for every
   step below. Steps 2–6 need zero Twilio involvement.
3. Add Deepgram only — log the transcript to console, confirm accuracy.
4. Add the LLM via the provider abstraction (start with GPT-5.4 mini) —
   log its response, confirm sensible replies.
5. Add Inworld TTS — this is the first full end-to-end loop, still over
   SmallWebRTC in the browser.
6. Add the real system prompt, at least one tool/function, and the timing
   instrumentation described below — all still local, still free.
7. Only now bring in Twilio: add the SID/Auth Token to `.env`, start
   ngrok, and swap the transport to Twilio via the same config switch
   used for SmallWebRTC. This step validates the real phone-call
   experience — it isn't where you debug the pipeline itself.

Flag each stage for review before moving to the next rather than
generating the whole pipeline in one pass.

**Local numbers are optimistic, not final.** Phone audio is narrowband
(8kHz mu-law) versus WebRTC's cleaner signal, and a real Twilio call
path adds hops a local peer-to-peer connection doesn't have. STT
accuracy and latency measured on SmallWebRTC will look better than what
a real call produces. Re-run the LLM bake-off and the test-plan metrics
over an actual Twilio call before treating any number as a final
decision — step 7 isn't just a formality, it's where the real numbers
come from.

## LLM bake-off

Once the full cascade loop works (post step 6), hold STT, TTS, and
transport constant and run the same test script against each LLM
candidate above, one at a time. Log per candidate:

- Time-to-first-token
- Cost per call (actual usage, not list price)
- Function-calling success rate (correct tool invocations ÷ attempts)
- Response quality on the same prompts (manual read, not just logs)

Don't declare a winner from one run — run the full test script per
candidate so the comparison is apples-to-apples, same as the cascade-
vs-S2S test.

## Production requirements

Not optional once this moves past prototype. Flag it if a change skips
any of these rather than silently letting it slide.

**Secrets** — env vars only, loaded via `.env` locally / a secrets
manager in production (Azure Key Vault or AWS Secrets Manager — already
on both). Never log API keys or full auth tokens.

**Webhook security** — validate Twilio's `X-Twilio-Signature` header on
every inbound webhook request before processing it.

**Resilience** — every external API call (Deepgram, the active LLM
provider, Inworld) needs a timeout and retry with exponential backoff. Define explicit
fallback behavior if a provider is down: a graceful message or clean
call termination, never a silent hang.

**Idempotency** — Twilio can redeliver webhooks. Handlers must not
double-process a retried request.

**Observability** — structured (JSON) logs per call, with a call ID
threading through every stage. The timing instrumentation (user-speech-
end, first-token, first-audio) is a permanent feature, not a one-off
test. Track latency as percentiles (P50/P95/P99), not just averages.

**Concurrency** — define and enforce a max concurrent call limit; reject
or queue gracefully beyond it rather than degrading silently.

**Graceful shutdown** — drain in-flight calls on deploy/restart. Never
hard-kill an active call.

**Testing** — unit tests for function-calling logic and pipeline stages,
not just manual call testing. Tests land alongside each build step, not
after it.

**Deployment** — Docker container, Nginx as reverse proxy/TLS
termination, PM2 or systemd for process management, hosted on Azure or
AWS. This matches the existing stack — don't introduce new infra without
a specific reason to.

**Data handling** — call transcripts/audio may be PII. Define a
retention policy and encrypt at rest. Revisit consent/recording
disclosure requirements once the application and its calling
jurisdiction are defined — this is still open and varies by use case.

## Code style and documentation

- One consistent style across the whole project — pick a formatter
  (Black) and linter (Ruff) for Python, run them before every commit.
  No mixed conventions between files or between sessions.
- Docstrings: one to three lines. State what the function does and why
  it exists, not a restatement of its signature. Skip the docstring
  entirely when the function's name already makes it obvious.
- Comments explain *why*, not *what* — the code itself should show what
  it's doing. A comment that just restates the next line is noise;
  delete it rather than write it.
- No comment block longer than the code it describes. If a function
  needs a paragraph of explanation, the function is doing too much —
  split it up instead of documenting around the complexity.
- Write for a human picking this up in six months, not for
  completeness. Short and clear beats long and thorough, every time.

## Working conventions

- Keep the cascade and S2S variants swappable via config, not
  duplicated codebases. The LLM inside the cascade is a third swap
  point, same principle — one abstraction, config picks the provider.
- Prefer small, reviewable commits per build step over large ones.
- **Never install anything without asking first.** This covers every
  package, tool, or runtime: `pip`/`uv`/`brew`/`npm` installs, new
  dependencies added to `pyproject.toml` or `requirements.txt`, virtualenv
  creation, Docker images, and CLIs like ngrok. State what you want to
  install and why, then wait for an explicit yes.
- **Explain every change, for a learner.** The user is learning as we
  build and is not yet familiar with agents, Pipecat, or the tools and
  libraries involved. After each change, say plainly what was done, why
  it was done, and what need it solves. Explain every import, library,
  tool, and term the first time it appears, in everyday language, with a
  small analogy where it helps. Stay to the point: elaborate on the
  unfamiliar, skip the obvious. One command or edit at a time.
- If something here conflicts with what's asked mid-session, flag the
  conflict rather than silently following whichever is newer.
