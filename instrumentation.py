"""Capture the agent once and export its spans to Phoenix and Arize AX."""

import logging
import os

from arize.otel import HTTPSpanExporter
from dotenv import load_dotenv
from openinference.instrumentation.langchain import LangChainInstrumentor
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from phoenix.otel import register

load_dotenv()

logger = logging.getLogger(__name__)
project_name = os.getenv("ARIZE_PROJECT_NAME", "se-interview")

# Phoenix keeps its configured endpoint and receives the same project/spans as AX.
tracer_provider = register(project_name=project_name, batch=True, verbose=False)

space_id = os.getenv("ARIZE_SPACE_ID")
api_key = os.getenv("ARIZE_API_KEY")
if space_id and api_key:
    try:
        arize_exporter = HTTPSpanExporter(
            endpoint=os.getenv(
                "ARIZE_COLLECTOR_ENDPOINT", "https://otlp.arize.com/v1/traces"
            ),
            space_id=space_id,
            api_key=api_key,
            timeout=10,
        )
        tracer_provider.add_span_processor(
            BatchSpanProcessor(arize_exporter),
            replace_default_processor=False,
        )
    except Exception:
        logger.warning("Arize AX tracing could not initialize; Phoenix remains enabled.")
else:
    logger.warning(
        "Arize AX tracing is disabled: set ARIZE_SPACE_ID and ARIZE_API_KEY. "
        "Phoenix tracing remains enabled."
    )

# LangChain instrumentation also covers LangGraph, ChatOpenAI, and tool calls.
LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
