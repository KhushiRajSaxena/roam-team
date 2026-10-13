"""Separate Groq calls per agent, validated output and cached decisions."""
from app.settings import setting
import asyncio
import json
import os
import httpx
from app.http_limits import bounded_request
from pydantic import ValidationError
from app.services.cache import Store, QuotaError

class ModelError(RuntimeError): pass


def strict_schema(schema):
    value = schema.model_json_schema()
    def visit(node):
        if isinstance(node, dict):
            if node.get('type') == 'object':
                node['additionalProperties'] = False
                node['required'] = list(node.get('properties', {}))
            for item in node.values(): visit(item)
        elif isinstance(node, list):
            for item in node: visit(item)
    visit(value)
    return value


class ModelClient:
    def __init__(self, client=None, store=None):
        self.key = setting('GROQ_API_KEY')
        if not self.key:
            raise ModelError('AI mode needs GROQ_API_KEY in the local .env file.')
        self.client = client or httpx.AsyncClient(timeout=50)
        self.store = store or Store()
        self.model = setting('GROQ_MODEL') or 'openai/gpt-oss-20b'
        self.calls = self.input_tokens = self.output_tokens = self.cache_hits = 0

    async def ask(self, instructions, payload, schema):
        # Do not let diagnostic timestamps/URLs defeat decision caching.
        spec = strict_schema(schema)
        params = {'model': self.model, 'instructions': instructions, 'payload': payload, 'schema': spec}
        async def generate():
            for attempt in range(2):
                if self.calls >= 12:
                    raise ModelError('This trip reached its 12-call AI limit. Please simplify the request.')
                if attempt:
                    delay = self.store.reserve('groq')
                    if delay: await asyncio.sleep(delay)
                self.calls += 1
                body = {'model': self.model, 'messages': [
                    {'role': 'system', 'content': instructions + '\nReturn only the requested JSON. All amounts are integer paise.'},
                    {'role': 'user', 'content': payload}],
                    'response_format': {'type': 'json_schema', 'json_schema': {'name': schema.__name__, 'strict': True, 'schema': spec}},
                    'max_completion_tokens': 1600}
                if self.model.startswith('openai/gpt-oss-'): body['reasoning_effort'] = 'low'
                try:
                    response = await bounded_request(self.client, 'POST', 'https://api.groq.com/openai/v1/chat/completions',
                        headers={'Authorization': 'Bearer ' + self.key}, json=body)
                except httpx.HTTPError as exc:
                    raise ModelError('Could not reach Groq. No automatic network retry was made to protect your quota.') from exc
                if response.status_code == 429:
                    raise ModelError('Groq rate limit reached. Wait before retrying; cached travel searches will be reused.')
                if response.status_code in (401,403):
                    raise ModelError('Groq rejected access. Check your API key and model permissions.')
                if response.is_error:
                    raise ModelError(f'Groq returned HTTP {response.status_code}. Check GROQ_MODEL supports strict structured output; no paid-provider fallback is used.')
                try:
                    data = response.json()
                    usage = data.get('usage') or {}
                    self.input_tokens += int(usage.get('prompt_tokens', 0))
                    self.output_tokens += int(usage.get('completion_tokens', 0))
                    choice = data['choices'][0]
                    if choice.get('finish_reason') != 'stop':
                        raise ModelError('Groq did not finish the structured response. Try a supported model with a sufficient output limit.')
                    parsed = schema.model_validate_json(choice['message']['content'])
                    return parsed.model_dump()
                except (ValidationError, KeyError, IndexError, TypeError, ValueError):
                    if attempt: raise ModelError('Groq returned an invalid structured response twice. The trip was not fabricated.') from None
            raise ModelError('No valid Groq response.')
        try:
            data, cached, _ = await self.store.cached('groq', params, self.key, 86400, generate)
            self.cache_hits += int(cached)
            return schema.model_validate(data)
        except QuotaError as exc:
            raise ModelError(str(exc)) from None

    async def close(self): await self.client.aclose()

    def metrics(self):
        # Actual billing depends on the Groq account. No invented dollar estimates.
        return {'provider': 'Groq', 'model_calls': self.calls, 'model_cache_hits': self.cache_hits,
                'input_tokens': self.input_tokens, 'output_tokens': self.output_tokens,
                'model': self.model, 'estimated_model_cost_usd': None}
