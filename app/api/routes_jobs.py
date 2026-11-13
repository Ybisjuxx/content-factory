import json
import logging
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models.job import Job, JobStatus, JobCreateRequest, JobResponse
from app.pipeline.orchestrator import VideoPipelineOrchestrator
from app.security import resolve_media_path, resolve_output_path, validate_webhook_url

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["Jobs & n8n Interoperability"])


@router.post("", response_model=JobResponse, status_code=202)
def create_job(
    req: JobCreateRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    """Submits a video editing job to the autonomous local production pipeline.

    Compatible with local n8n HTTP Request / Webhook triggers.
    """
    input_p = resolve_media_path(req.input_video_path)
    output_p = resolve_output_path(req.output_video_path)
    webhook = validate_webhook_url(req.n8n_webhook_url)
    music = str(resolve_media_path(req.music_track_path)) if req.music_track_path else None

    options = {
        "enable_broll": req.enable_broll,
        "enable_svg_cards": req.enable_svg_cards,
        "enable_subtitles": req.enable_subtitles,
        "subtitle_sync_mode": req.subtitle_sync_mode or "word_by_word",
        "enable_music_ducking": req.enable_music_ducking,
        "music_track_path": music,
        "ollama_model": req.ollama_model,
        "n8n_webhook_url": webhook,
    }

    job = Job(
        input_path=str(input_p),
        output_path=str(output_p) if output_p else None,
        status=JobStatus.QUEUED,
        current_step="Queued for processing",
        n8n_webhook_url=webhook,
        options_json=json.dumps(options)
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    # Launch in background task so API responds immediately to n8n / caller
    orchestrator = VideoPipelineOrchestrator()
    background_tasks.add_task(
        orchestrator.run_pipeline,
        job_id=job.id,
        input_video_path=job.input_path,
        output_video_path=job.output_path,
        options=options,
    )

    return _job_to_response(job)


@router.get("", response_model=List[JobResponse])
def list_jobs(
    status: Optional[JobStatus] = None,
    limit: int = 50,
    session: Session = Depends(get_session)
):
    """Lists recent video factory jobs."""
    query = select(Job).order_by(Job.created_at.desc()).limit(limit)
    if status:
        query = query.where(Job.status == status)
    jobs = session.exec(query).all()
    return [_job_to_response(j) for j in jobs]


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, session: Session = Depends(get_session)):
    """Retrieves detailed status, progress, and EDL summary for a given job."""
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_response(job)


@router.get("/{job_id}/download")
def download_rendered_video(job_id: str, session: Session = Depends(get_session)):
    """Downloads or streams the final rendered MP4 video."""
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.COMPLETED or not job.output_path or not Path(job.output_path).exists():
        raise HTTPException(status_code=400, detail="Rendered video is not yet available or failed.")

    return FileResponse(
        path=job.output_path,
        filename=Path(job.output_path).name,
        media_type="video/mp4"
    )


@router.post("/{job_id}/cancel")
def cancel_job(job_id: str, session: Session = Depends(get_session)):
    """Cancels a queued or running job."""
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
        raise HTTPException(status_code=409, detail=f"El job ya terminó ({job.status.value}).")

    # The orchestrator polls this status between stages and stops cooperatively.
    job.status = JobStatus.CANCELLED
    job.current_step = "Cancelled by user"
    session.add(job)
    session.commit()
    return {"status": "cancelled", "job_id": job_id}


def _job_to_response(job: Job) -> JobResponse:
    edl_summary = None
    if job.director_summary_json:
        try:
            edl_summary = json.loads(job.director_summary_json)
        except Exception:
            pass

    return JobResponse(
        id=job.id,
        input_path=job.input_path,
        output_path=job.output_path,
        status=job.status,
        progress=job.progress,
        current_step=job.current_step,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
        execution_time_seconds=job.execution_time_seconds,
        edl_summary=edl_summary,
    )
