"""Microservicio de Guardrails (FastAPI, puerto interno 8080)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from .audit import AuditLogEntry, AuditSink, default_sink
import os

from .llm import LlmClassifier, default_classifier, needs_llm_input_check, topic_check_enabled
from .rules import FALLBACK_RESPONSE, Verdict, check_input, check_output

_UNSET = object()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


class InputRequest(BaseModel):
    session_id: str = ""
    message: str = ""


class InputResponse(BaseModel):
    allowed: bool
    reason: str | None = None


class OutputRequest(BaseModel):
    session_id: str = ""
    response: str = ""


class OutputResponse(BaseModel):
    allowed: bool
    sanitized_response: str


def create_app(sink: AuditSink | None = None, classifier: LlmClassifier | None | object = _UNSET) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.audit = sink or default_sink()
        # Por defecto el LLM solo se activa si GUARDRAILS_LLM_URL está definida (los tests no lo usan).
        app.state.llm = default_classifier() if classifier is _UNSET else classifier
        yield
        close = getattr(app.state.audit, "close", None)
        if close:
            await close()

    app = FastAPI(title="UNAB Chatbot Guardrails", version="1.0.0", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.post("/validate-input", response_model=InputResponse)
    async def validate_input(req: InputRequest) -> InputResponse:
        verdict = check_input(req.message)
        mode = os.getenv("GUARDRAILS_LLM_INPUT", "suspicious")
        if (verdict.allowed and app.state.llm is not None and needs_llm_input_check(req.message, mode)
                and await app.state.llm.is_attack(req.message)):
            verdict = Verdict(False, "input_injection", "LLM: posible manipulación del asistente")
        if (verdict.allowed and app.state.llm is not None
                and topic_check_enabled(os.getenv("GUARDRAILS_LLM_TOPIC", "on"))
                and await app.state.llm.is_off_topic_question(req.message)):
            verdict = Verdict(False, "input_scope", "LLM: pregunta fuera del ámbito académico")
        if not verdict.allowed:
            await app.state.audit.write(
                AuditLogEntry.create(req.session_id, verdict.rejection_type, verdict.reason, req.message))
            return InputResponse(allowed=False, reason=verdict.reason)
        return InputResponse(allowed=True, reason=None)

    @app.post("/validate-output", response_model=OutputResponse)
    async def validate_output(req: OutputRequest) -> OutputResponse:
        verdict = check_output(req.response)
        if verdict.allowed and app.state.llm is not None and await app.state.llm.is_off_topic(req.response):
            verdict = Verdict(False, "output_scope", "LLM: respuesta fuera del ámbito académico")
        if not verdict.allowed:
            await app.state.audit.write(
                AuditLogEntry.create(req.session_id, verdict.rejection_type, verdict.reason, req.response))
            return OutputResponse(allowed=False, sanitized_response=FALLBACK_RESPONSE)
        return OutputResponse(allowed=True, sanitized_response=req.response)

    return app


app = create_app()
