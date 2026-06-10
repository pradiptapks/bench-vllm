#!/usr/bin/env python3
# -*- mode: python; indent-tabs-mode: nil; python-indent-level: 4 -*-
# vim: autoindent tabstop=4 shiftwidth=4 expandtab softtabstop=4 filetype=python

"""
Lightweight mock OpenAI-compatible server for CPU-smoke testing.

Implements the minimum endpoints needed by GuideLLM:
  GET  /health                  — liveness check
  GET  /v1/models               — model listing
  POST /v1/chat/completions     — streaming/non-streaming chat
  POST /v1/completions          — legacy completions

Produces deterministic, syntactically valid responses with realistic
token-count metadata so that GuideLLM and vllm-post-process.py can
exercise the full benchmark pipeline without loading a real model.
"""

import argparse
import json
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler


_MODEL_NAME = "mock-model"
_MOCK_REPLY = "This is a mock response for smoke testing the benchmark pipeline."


def _ts():
    return int(time.time())


def _chat_completion(body):
    """Return a non-streaming ChatCompletion response."""
    n_prompt = body.get("max_tokens", 64)
    n_completion = len(_MOCK_REPLY.split())
    return {
        "id": "chatcmpl-" + uuid.uuid4().hex[:8],
        "object": "chat.completion",
        "created": _ts(),
        "model": body.get("model", _MODEL_NAME),
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": _MOCK_REPLY},
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": n_prompt,
            "completion_tokens": n_completion,
            "total_tokens": n_prompt + n_completion
        }
    }


def _chat_completion_stream(body):
    """Yield SSE chunks for a streaming ChatCompletion."""
    model = body.get("model", _MODEL_NAME)
    cid = "chatcmpl-" + uuid.uuid4().hex[:8]

    # role chunk
    yield _sse({
        "id": cid, "object": "chat.completion.chunk",
        "created": _ts(), "model": model,
        "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]
    })
    # token chunks
    for token in _MOCK_REPLY.split():
        yield _sse({
            "id": cid, "object": "chat.completion.chunk",
            "created": _ts(), "model": model,
            "choices": [{"index": 0, "delta": {"content": token + " "}, "finish_reason": None}]
        })
        time.sleep(0.01)
    # stop chunk
    yield _sse({
        "id": cid, "object": "chat.completion.chunk",
        "created": _ts(), "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
    })
    yield "data: [DONE]\n\n"


def _sse(obj):
    return "data: " + json.dumps(obj) + "\n\n"


class MockHandler(BaseHTTPRequestHandler):

    model_name = _MODEL_NAME

    def log_message(self, fmt, *args):
        pass

    def _send_json(self, code, obj):
        payload = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"status": "ok"})
        elif self.path == "/v1/models":
            self._send_json(200, {
                "object": "list",
                "data": [{
                    "id": self.model_name,
                    "object": "model",
                    "created": _ts(),
                    "owned_by": "mock"
                }]
            })
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        if self.path in ("/v1/chat/completions", "/v1/completions"):
            if body.get("stream"):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                for chunk in _chat_completion_stream(body):
                    self.wfile.write(chunk.encode())
                    self.wfile.flush()
            else:
                self._send_json(200, _chat_completion(body))
        else:
            self._send_json(404, {"error": "not found"})


def main():
    parser = argparse.ArgumentParser(description="Mock OpenAI-compatible server")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--model", type=str, default=_MODEL_NAME)
    args = parser.parse_args()

    MockHandler.model_name = args.model
    server = HTTPServer(("0.0.0.0", args.port), MockHandler)
    print("Mock server listening on port %d (model=%s)" % (args.port, args.model))
    server.serve_forever()


if __name__ == "__main__":
    main()
