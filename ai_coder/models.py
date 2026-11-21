from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Requirement(Contract):
    id: str = Field(pattern=r'^R[1-9][0-9]*$')
    text: str = Field(min_length=1, max_length=3000)


class Request(Contract):
    description: str = Field(min_length=1, max_length=12000)
    requirements: list[Requirement] = Field(min_length=1, max_length=30)

    @field_validator('requirements')
    @classmethod
    def unique_ids(cls, items):
        if len({r.id for r in items}) != len(items):
            raise ValueError('Requirement IDs must be unique')
        return items


class Acceptance(Contract):
    requirement_id: str
    criterion: str = Field(min_length=1)
    method: Literal['automated', 'startup', 'manual']


class Interface(Contract):
    signature: str
    behavior: str
    returns: str
    errors: str


class Spec(Contract):
    requirements: list[Requirement]
    interfaces: list[Interface] = Field(min_length=1)
    ui_behavior: str = Field(min_length=1)
    ui_callbacks: list[str] = Field(default_factory=list)
    acceptance: list[Acceptance] = Field(min_length=1)

    def check_request(self, request: Request):
        if self.requirements != request.requirements:
            raise ValueError('Planner changed original requirements')
        if {a.requirement_id for a in self.acceptance} != {r.id for r in request.requirements}:
            raise ValueError('Acceptance criteria must cover every requirement')


class File(BaseModel):
    model_config = ConfigDict(extra='forbid')
    path: str
    content: str = Field(min_length=1, max_length=100000)


class Application(Contract):
    files: list[File] = Field(min_length=3, max_length=3)

    @model_validator(mode='after')
    def required_files(self):
        if {f.path for f in self.files} != {'app.py', 'logic.py', 'README.md'}:
            raise ValueError('Application must contain app.py, logic.py and README.md')
        return self


class Coverage(Contract):
    requirement_id: str
    method: Literal['automated', 'startup', 'manual']
    test_names: list[str]
    explanation: str


class TestFile(File):
    __test__ = False
    path: str = Field(pattern=r'^tests/test_[a-zA-Z0-9_]+\.py$')


class TestSuite(Contract):
    __test__ = False
    files: list[TestFile] = Field(min_length=1, max_length=10)
    coverage: list[Coverage]


class Execution(Contract):
    status: Literal['PASSED', 'FAILED', 'NOT RUN', 'ERROR']
    detail: str
    exit_code: int | None = None
    collected: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    startup_ok: bool = False
