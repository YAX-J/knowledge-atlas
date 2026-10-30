"""Shared validation for provider-reported decision probabilities."""
from pydantic import BaseModel, ConfigDict, Field


class JudgeError(Exception):
    """A static error code, never provider text or credentials."""


class Choice(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    type: str
    choice: str
    confidence: float = Field(ge=0, le=1)
    probabilities: dict[str, float]


def validate_choices(answers, questions):
    if not isinstance(answers, dict) or set(answers) != set(questions):
        raise ValueError('Unexpected decision keys')
    validated = {}
    for name, question in questions.items():
        item = Choice.model_validate(answers[name])
        options = set(question['criteria'])
        if item.type != 'choice' or item.choice not in options or set(item.probabilities) != options:
            raise ValueError('Unexpected choice')
        if any(not 0 <= value <= 1 for value in item.probabilities.values()) or abs(sum(item.probabilities.values()) - 1) > .01:
            raise ValueError('Invalid probabilities')
        validated[name] = item.model_dump()
    return validated
