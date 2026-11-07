import pytest
from app.models.job import Job, JobStatus, EditSegment, VisualCue, DirectorPlan
from app.models.asset import Asset, AssetType


def test_job_and_plan_models():
    seg1 = EditSegment(start=0.0, end=2.0, keep=False, reason="False start", text="Hello I am...")
    seg2 = EditSegment(start=2.0, end=5.5, keep=True, reason="Good take", text="Hello I am testing the local factory.")
    
    cue = VisualCue(
        timestamp_start=2.5,
        timestamp_end=4.5,
        asset_type="broll",
        query_or_topic="coding python"
    )

    plan = DirectorPlan(
        title="Test Production",
        hook="Hello I am testing",
        summary="Testing local factory",
        edit_decision_list=[seg1, seg2],
        visual_cues=[cue],
        removed_takes_count=1,
        estimated_duration=3.5
    )

    assert len(plan.edit_decision_list) == 2
    assert plan.removed_takes_count == 1
    assert plan.visual_cues[0].asset_type == "broll"


def test_asset_model():
    asset = Asset(
        name="cyberpunk_city",
        file_path="/storage/broll/cyberpunk_city.mp4",
        asset_type=AssetType.BROLL,
        tags="cyberpunk,city,neon,future",
        duration_seconds=10.0,
        width=1080,
        height=1920,
        is_vertical=True
    )
    assert asset.is_vertical is True
    assert "neon" in asset.tags
