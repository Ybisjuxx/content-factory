import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field
from pydantic import BaseModel, Field as PydanticField


class JobStatus(str, Enum):
    QUEUED = "queued"
    TRANSCRIBING = "transcribing"
    DIRECTING = "directing"
    SELECTING_ASSETS = "selecting_assets"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EditSegment(BaseModel):
    start: float = PydanticField(..., description="Start timestamp in seconds")
    end: float = PydanticField(..., description="End timestamp in seconds")
    keep: bool = PydanticField(..., description="Whether to include this take segment in the final cut")
    reason: str = PydanticField(default="", description="Reason for keeping or pruning (e.g. repetition, stumble, good take)")
    text: str = PydanticField(default="", description="Transcript text for this segment")


class VisualCue(BaseModel):
    timestamp_start: float = PydanticField(..., description="Start timestamp in final video time")
    timestamp_end: float = PydanticField(..., description="End timestamp in final video time")
    asset_type: str = PydanticField(default="broll", description="'broll' or 'svg_card'")
    query_or_topic: str = PydanticField(..., description="Search query for b-roll or topic for card")
    card_type: Optional[str] = PydanticField(default="stat", description="'stat', 'takeaway', 'quote'")
    card_title: Optional[str] = PydanticField(default=None)
    card_content: Optional[str] = PydanticField(default=None)
    asset_path: Optional[str] = PydanticField(default=None)


class DirectorPlan(BaseModel):
    title: str = PydanticField(default="Untitled Video")
    hook: str = PydanticField(default="")
    summary: str = PydanticField(default="")
    edit_decision_list: List[EditSegment] = PydanticField(default_factory=list)
    visual_cues: List[VisualCue] = PydanticField(default_factory=list)
    removed_takes_count: int = 0
    estimated_duration: float = 0.0


class JobBase(SQLModel):
    input_path: str
    output_path: Optional[str] = None
    status: JobStatus = Field(default=JobStatus.QUEUED)
    progress: float = Field(default=0.0)
    current_step: str = Field(default="Enqueued")
    error_message: Optional[str] = None
    n8n_webhook_url: Optional[str] = None
    options_json: str = Field(default="{}")


class Job(JobBase, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    transcript_json: Optional[str] = Field(default=None)
    edl_json: Optional[str] = Field(default=None)
    director_summary_json: Optional[str] = Field(default=None)
    execution_time_seconds: Optional[float] = Field(default=None)


class JobCreateRequest(BaseModel):
    input_video_path: str
    output_video_path: Optional[str] = None
    n8n_webhook_url: Optional[str] = None
    enable_broll: bool = True
    enable_svg_cards: bool = True
    enable_subtitles: bool = True
    enable_music_ducking: bool = True
    music_track_path: Optional[str] = None
    ollama_model: Optional[str] = None


class JobResponse(BaseModel):
    id: str
    input_path: str
    output_path: Optional[str] = None
    status: JobStatus
    progress: float
    current_step: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    execution_time_seconds: Optional[float] = None
    edl_summary: Optional[Dict[str, Any]] = None
