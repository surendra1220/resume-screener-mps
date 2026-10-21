from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

Category = Literal['Mandatory', 'Good to Have']
Status = Literal['Matched', 'Partial Match', 'Claimed but Unevidenced', 'Missing']


class Requirement(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=200)
    category: Category = 'Mandatory'
    description: str = Field(min_length=1, max_length=2000)
    source: str = Field(default='', max_length=4000)
    alternatives: list[str] = Field(default_factory=list, max_length=30)
    all_of: list[str] = Field(default_factory=list, max_length=20)
    weight: int = Field(default=1, ge=1, le=10)
    knowledge_ok: bool = False


class AnalyzeRequest(BaseModel):
    resume_text: str = Field(min_length=40, max_length=120000)
    jd_text: str = Field(min_length=40, max_length=120000)
    requirements: list[Requirement] = Field(min_length=1, max_length=60)
    jd_label: str = Field(default='Custom JD', max_length=200)
    candidate_label: str = Field(default='Candidate', max_length=200)


class ReportRequest(BaseModel):
    report: dict
