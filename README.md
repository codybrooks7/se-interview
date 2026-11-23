# Travel Assistant with Phoenix Tracing

A LangGraph travel assistant exposed through FastAPI. GPT-4o can search the web with DuckDuckGo or call a deterministic trip-budget calculator. OpenInference captures the agent workflow, model calls, and tool calls for inspection in local Phoenix, with optional export to Arize AX.

## What we added

- **Trip-budget tool:** `calculate_trip_budget` returns a structured breakdown, total, budget status, and remaining budget. The model chooses when to invoke it.
- **Phoenix tracing:** `instrumentation.py` registers the tracer provider and instruments LangChain/LangGraph before the model and graph are created.
- **Optional Arize AX tracing:** when both Arize credentials are set, a second exporter sends the same spans to AX.
- **Dependency updates:** Python support is restricted to 3.11–3.14; FastAPI and Uvicorn requirements were updated and tracing dependencies added to the Poetry lockfile.

## Prerequisites

- Python 3.12 recommended (the app supports Python `>=3.11,<3.15`).
- [Poetry](https://python-poetry.org/docs/#installation).
- An OpenAI API key with API access and available billing/credits.
- Two Terminal windows for the servers, plus a third for sending requests.

The Phoenix **server** runs in a separate Python environment. The app's Poetry environment contains only the tracing integrations. This avoids conflicts between the Phoenix server's dependencies and the starter app's older LangChain/OpenAI stack.

## 1. Set up the app

```bash
git clone https://github.com/codybrooks7/se-interview.git
cd se-interview
poetry env use python3.12
poetry install
cp .env.example .env
```

If you already have the repository and a `.env`, keep that existing file. Run Poetry commands from the folder containing `pyproject.toml`.

Edit `.env` with your own settings. For local Phoenix only, use:

```dotenv
OPENAI_API_KEY=your_openai_api_key_here
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006
ARIZE_PROJECT_NAME=se-interview
ARIZE_API_KEY=
ARIZE_SPACE_ID=
```

`ARIZE_PROJECT_NAME` names the project in Phoenix as well as AX. Leave both AX credential fields empty when using only Phoenix; replace the example values copied from `.env.example`. Keep `.env` private; it is ignored by Git.

For optional Arize AX export, set `ARIZE_API_KEY` and `ARIZE_SPACE_ID` to your own account's values. `ARIZE_COLLECTOR_ENDPOINT` defaults to `https://otlp.arize.com/v1/traces`. With both credentials present, the app exports to Phoenix and AX; with either missing, it logs an AX-disabled warning and continues with Phoenix.

## 2. Start Phoenix — Terminal 1

Install the server once in its own environment:

```bash
python3.12 -m venv ~/phoenix-server
source ~/phoenix-server/bin/activate
python -m pip install --upgrade pip
python -m pip install arize-phoenix
phoenix serve
```

On later runs, use only:

```bash
source ~/phoenix-server/bin/activate
phoenix serve
```

Leave this window running. Open [Phoenix](http://localhost:6006) in your browser. See [Phoenix documentation](https://arize.com/docs/phoenix) for server configuration and evaluation guidance.

## 3. Start the app — Terminal 2

From the cloned repository folder:

```bash
poetry run uvicorn api:app --reload
```

Leave this window running too. The app is at [http://localhost:8000](http://localhost:8000); its interactive API page is at [http://localhost:8000/docs](http://localhost:8000/docs). You can use that page to send requests without Terminal quoting.

## 4. Send a request — Terminal 3

Check the server:

```bash
curl http://localhost:8000/health
```

Expected response: `{"status":"ok"}`.

Try the budget tool:

```bash
curl --max-time 60 -H 'Content-Type: application/json' -d '{"message":"My budget is $1,500 for a 3-night trip. Flight is $400, hotel is $200 per night, and daily spending is $100. Use the trip budget calculator and show the breakdown."}' http://localhost:8000/chat
```

The calculation should be **$1,400 total**, leaving **$100**. The API returns an object with a `response` string; the exact wording varies.

Try web search:

```bash
curl --max-time 60 -H 'Content-Type: application/json' -d '{"message":"Search the web for attractions in Chicago and summarize a few options."}' http://localhost:8000/chat
```

### Budget assumptions

The calculator takes total flight cost, nightly hotel cost, nights, daily spending, and total budget. All amounts must use the same currency.

```text
hotel total = nightly hotel cost × nights
daily spending total = daily spending × (nights + 1)
estimated total = flight cost + hotel total + daily spending total
remaining = budget − estimated total
```

`within_budget` is true when the total is less than or equal to the budget. The tool uses supplied estimates; it does not fetch live prices or book travel. It currently has no explicit validation for negative values or currency conversion.

## 5. Inspect traces in Phoenix

1. Open Phoenix and select the `se-interview` project (or your `ARIZE_PROJECT_NAME`). Older runs may be under `default`.
2. Send a new `/chat` request and allow a few seconds for batched spans to arrive.
3. Open the trace and inspect `LangGraph`, `ChatOpenAI`, and any tool spans. Budget requests should show `calculate_trip_budget` when the agent chooses it.
4. Inspect tool arguments, structured results, model inputs/outputs, and timing.

A **trace** groups the work for one request; a **span** records one operation within it. OpenTelemetry supplies the tracing/export mechanism, while OpenInference supplies AI-specific attributes such as model messages and tool information.

For interaction datasets, use completed `LangGraph` spans. Their input is the original message state, and their output is the resulting message state including the final assistant response. A table preview may show the same first user message in both columns; open the output to see the additional messages. Exporting every span mixes framework internals, tools, and model calls into separate examples.

### Evaluation status

Phoenix datasets and evaluators configured through its UI live in that Phoenix instance; they are not included in this Git repository. This repository does not yet include an evaluation runner or code that attaches frustration scores to spans. Creating or attaching a dataset evaluator alone does not score the historical source traces. To complete that workflow, run the evaluation, log results to the source span IDs, then filter the scored spans and save frustrated interactions as a dataset.

If an evaluator or Playground call needs a model, configure its provider credentials in Phoenix separately. The app's `.env` does not automatically configure the separately running Phoenix server.

## How the agent works

1. `/chat` receives one user message and invokes the graph.
2. The model receives the system instruction, message state, and available tools.
3. If the model requests a tool, the graph executes it and appends the tool result.
4. The graph calls the model again until it produces a final response.
5. FastAPI returns that final response.

Each `/chat` call starts a fresh message state; the API does not retain conversation history across requests.

## Project files

| File | Purpose |
| --- | --- |
| `agent.py` | LangGraph workflow, web-search tool, and budget calculator |
| `instrumentation.py` | Phoenix tracer registration, optional AX exporter, and LangChain instrumentation |
| `api.py` | `/chat` and `/health` endpoints |
| `.env.example` | Example app configuration; use your own values in `.env` |
| `pyproject.toml`, `poetry.lock` | App dependencies and locked versions |

## Troubleshooting

- **Poetry cannot find `pyproject.toml`:** change into the cloned `se-interview` folder.
- **Wrong Python version:** run `poetry env use python3.12`, then `poetry install`. Check with `poetry run python --version`.
- **Missing API key:** check `OPENAI_API_KEY` in the app's `.env` and restart the app.
- **Cannot connect to port 8000 or 6006:** confirm the corresponding server is running in its Terminal window.
- **Terminal shows `quote>`:** press Control+C and paste the entire request command again, using straight quotes.
- **No traces:** check the Phoenix collector endpoint, project name, time filter, and app logs. Restart the app after configuration changes.
- **Request stalls or fails:** inspect the app logs for OpenAI or web-search errors. The health endpoint does not verify model or search access.

Stop either server with Control+C in its Terminal window.
