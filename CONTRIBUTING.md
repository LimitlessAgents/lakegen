# Contributing to LakeGen

Thanks for wanting to help. This is the process we use so work stays coordinated and nothing gets built in isolation.

## 1. Start with an issue

If there is no issue for the work you want to do, [open one](https://github.com/LimitlessAgents/lakegen/issues/new) first. Do not open a pull request until an issue exists and maintainers have assigned it to you.

If an issue already exists, comment there instead of filing a duplicate.

## 2. Discuss the approach

This is not a test. We talk first so you don't spend time building something we'll have to turn down later.

Share whatever you have in mind — even a rough sketch is great. If the approach has holes, that's fine; that's what the thread is for. We'll figure it out together until we're confident it's the right thing to build.

## 3. Wait for assignment

Once maintainers approve the solution, they will assign the issue to you. That assignment is the green light to start coding.

Unassigned issues are still being decided. Please do not send a PR for them.

## 4. Open a pull request

After the issue is assigned, implement the agreed solution and open a PR.

Every PR description must end with a closing keyword so GitHub links and closes the issue on merge. For example:

```
Closes #100
```

Use the issue number you were assigned. One issue per PR unless maintainers say otherwise.

## Setting Up Development Environment

Follow these steps in order to run LakeGen on your machine with hot reload.

### Step 1: Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- Node.js and npm
- PostgreSQL. The Python driver needs the PostgreSQL client library (`libpq`), which a normal PostgreSQL install includes.
- An OpenAI or OpenAI-compatible API key

### Step 2: Clone the repository

```bash
git clone https://github.com/LimitlessAgents/lakegen.git
cd lakegen
```

To send changes, fork the repository first and clone your fork instead.

### Step 3: Install Python dependencies

```bash
uv sync
```

### Step 4: Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and set these two variables (`LAKEGEN_DATABASE_URL` is commented out in the example, so remove the `#`):

```dotenv
OPENAI_API_KEY=your-api-key
LAKEGEN_DATABASE_URL=postgresql://lakegen:lakegen@localhost:5432/lakegen
```

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes | API key used for inference. |
| `LAKEGEN_DATABASE_URL` | Yes | PostgreSQL connection string. The value above matches Step 5. |
| `OPENAI_BASE_URL` | No | Custom OpenAI-compatible endpoint, such as OpenRouter or a proxy. |
| `OPENAI_MODEL` | No | Model to use. Defaults to `gpt-4o-mini`. |

`.env` is ignored by git, so your key is never committed.

### Step 5: Start PostgreSQL

With Docker, this creates the user and database from Step 4:

```bash
docker run --name lakegen-postgres -d -p 5432:5432 -e POSTGRES_USER=lakegen -e POSTGRES_PASSWORD=lakegen -e POSTGRES_DB=lakegen postgres:16-alpine
```

Next time, start it again with `docker start lakegen-postgres`.

If you already run PostgreSQL yourself, create the same user and database instead (or change `LAKEGEN_DATABASE_URL` to match yours):

```bash
psql -U postgres -c "CREATE USER lakegen WITH PASSWORD 'lakegen'"
psql -U postgres -c "CREATE DATABASE lakegen OWNER lakegen"
```

LakeGen creates its tables when the API starts, so the database can be empty.

### Step 6: Run the API locally

From the repository root:

```bash
uv run uvicorn lakegen.api.app:app --reload
```

The API runs at [http://localhost:8000](http://localhost:8000).

### Step 7: Run the web application locally

In a second terminal:

```bash
cd apps/web
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). It forwards `/v1` and `/health` to the API.

### Step 8: Verify the health endpoint

The health endpoint is [http://localhost:8000/health](http://localhost:8000/health):

```bash
curl http://localhost:8000/health
```

You should see `{"status":"ok"}`.

### Step 9: Run the test suite

From the repository root:

```bash
uv run pytest
```

The tests need neither PostgreSQL nor an API key.

## Questions

If you are unsure whether something needs an issue, open one anyway. We would rather talk it through than have you spend time on work we cannot take.
