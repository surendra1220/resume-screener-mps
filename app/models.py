from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator

Category = Literal['Mandatory', 'Good to Have']
Status = Literal['Matched', 'Partial Match', 'Claimed but Unevidenced', 'Missing']


class Requirement(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(default='custom-req', max_length=60)
    name: str = Field(default='Requirement', max_length=200)
    category: Category = 'Mandatory'
    description: str = Field(default='Requirement expectation', max_length=2000)
    source: str = Field(default='', max_length=4000)
    alternatives: list[str] = Field(default_factory=list, max_length=30)
    all_of: list[str] = Field(default_factory=list, max_length=20)
    weight: int = Field(default=1, ge=1, le=10)
    knowledge_ok: bool = False

    @field_validator('id', mode='before')
    @classmethod
    def _coerce_id(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return 'custom-req'
        return v.strip() if isinstance(v, str) else str(v)

    @field_validator('name', mode='before')
    @classmethod
    def _coerce_name(cls, v):
        """Guarantee a non-empty name so no code path can ever trigger a validation error."""
        if isinstance(v, str):
            v = v.strip()
        return v if v else 'Requirement'

    @field_validator('description', mode='before')
    @classmethod
    def _coerce_description(cls, v):
        """Guarantee a non-empty description preserving existing whitespace when present."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return 'Requirement expectation'
        return v


class AnalyzeRequest(BaseModel):
    resume_text: str = Field(min_length=40, max_length=120000)
    jd_text: str = Field(min_length=40, max_length=120000)
    requirements: list[Requirement] = Field(min_length=1, max_length=60)
    jd_label: str = Field(default='Custom JD', max_length=200)
    candidate_label: str = Field(default='Candidate', max_length=200)
    resume_filename: str | None = Field(default=None, max_length=200)


class ReportRequest(BaseModel):
    report: dict
