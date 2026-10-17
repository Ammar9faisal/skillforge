from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


def timestamp():
    return datetime.now(timezone.utc)


class InputModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class CreateTask(InputModel):
    title: Title


class CheckpointInput(InputModel):
    note: Note = ''


class Checkpoint(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    position: int
    note: str = ''
    reference_image: str
    created_at: datetime = Field(default_factory=timestamp)


VisibleText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class TutorialStep(InputModel):
    step_id: int = Field(ge=1, le=24, strict=True)
    title: Title
    instruction: VisibleText
    reference_image: str = Field(pattern=r'^checkpoint_[0-9a-f]{32}\.jpg$')
    verification_criteria: list[VisibleText] = Field(min_length=1, max_length=12)
    safety_notes: list[VisibleText] = Field(max_length=12)


class TutorialOutput(InputModel):
    steps: list[TutorialStep] = Field(min_length=2, max_length=24)

    def validate_checkpoints(self, checkpoints):
        if len(self.steps) != len(checkpoints):
            raise ValueError('Return exactly one step for every supplied checkpoint.')
        for step, checkpoint in zip(self.steps, checkpoints):
            if step.step_id != checkpoint.position or step.reference_image != checkpoint.reference_image:
                raise ValueError('Step IDs and reference_image names must match the supplied checkpoints in order.')
        return self


class SavedTutorial(TutorialOutput):
    model: str
    generated_at: datetime = Field(default_factory=timestamp)


class Task(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    title: str
    created_at: datetime = Field(default_factory=timestamp)
    updated_at: datetime = Field(default_factory=timestamp)
    checkpoints: list[Checkpoint] = Field(default_factory=list)
    tutorial: SavedTutorial | None = None


class VerificationOutput(InputModel):
    status: Literal['PASS', 'FAIL', 'UNCERTAIN']
    expected: VisibleText
    observed: VisibleText
    feedback: VisibleText
    confidence: Literal['low', 'medium', 'high']


class SessionInput(InputModel):
    session_id: str | None = Field(default=None, pattern=r'^[0-9a-f]{32}$')
    tutorial_version: datetime


class VerifyInput(InputModel):
    session_id: str = Field(pattern=r'^[0-9a-f]{32}$')
    step_id: int = Field(ge=1, le=24, strict=True)
