"""Small provider-independent structured-output spike, not a conversational model.

A future model transport must implement complete_json. Validation is deliberately
separate from the provider so malformed results can be tested without network use.
"""

from typing import Protocol, TypeVar
import json

from pydantic import BaseModel

Output = TypeVar("Output", bound=BaseModel)


def strict_json(raw: str):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("Non-finite JSON value")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)


class JsonTransport(Protocol):
    async def complete_json(self, prompt: str, schema: dict) -> str: ...


async def validated_output(
    transport: JsonTransport, prompt: str, output_type: type[Output]
) -> Output:
    raw = await transport.complete_json(prompt, output_type.model_json_schema())
    result = output_type.model_validate_json(raw, strict=True)
    strict_json(raw)
    return result
