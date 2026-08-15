<p align="center">
  <img src="static/logo.png" alt="LakeGen logo" width="180" />
</p>

<h1 align="center">LakeGen</h1>

Lakehouses are powerful — and often painful to manage. Catalogs, namespaces, tables, credentials, connectors… there's a lot to keep straight, and it gets messy fast.

**LakeGen** is an AI agent that aims to make managing lakehouses simpler. Talk to it in plain language, and let it handle the busywork. We're starting with [Apache Iceberg](https://iceberg.apache.org/).

## Heads up — we're early

This project is still in its early stages. Things will change. APIs will shift. Some pieces aren't ready yet.

That's okay. We're building in the open, and we'd love for you to be part of it.

## Try it

You'll need Python 3.13+ and Node.js. The agent talks to an OpenAI-compatible API, so set `OPENAI_API_KEY` (and `OPENAI_BASE_URL` if you aren't using OpenAI directly) in a `.env` at the repo root.

```bash
uv sync
uvicorn lakegen.api.app:app --reload
```

In another terminal:

```bash
cd apps/web
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Add a catalog (AWS Glue, Iceberg REST, or SQL), then chat with the agent in plain language — list namespaces, describe tables, inspect snapshots, and so on.

The UI proxies `/v1` to the API on port 8000. Health: `GET /health`.

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENAI_API_KEY` | — | Inference credentials |
| `OPENAI_BASE_URL` | OpenAI | Override for OpenRouter or other OpenAI-compatible hosts |
| `LAKEGEN_CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173` | Comma-separated browser origins |
| `LAKEGEN_MAX_IN_FLIGHT_TURNS` | `8` | Cap concurrent agent turns |

## Contributing

Whether you're fixing a typo, raising an issue, sketching an idea, or diving into the code — you're welcome here.

You don't need to be an expert. Curiosity is enough. If something feels unclear or broken, say so. If you have a thought on where this should go, we'd love to hear it.

If you'd like to contribute, start with [CONTRIBUTING.md](CONTRIBUTING.md) — it's a short read and will save you time.