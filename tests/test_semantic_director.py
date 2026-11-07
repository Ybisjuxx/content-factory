import pytest
from app.services.semantic_director import SemanticDirector
from app.models.job import DirectorPlan


def test_semantic_director_heuristic_pruning():
    director = SemanticDirector()
    
    # Simulate a raw multi-take recording with stumbles and false starts
    mock_transcript = {
        "duration": 18.0,
        "language": "en",
        "full_text": "Um hello. Today we are... Today we are announcing the autonomous video engine. Um yeah.",
        "segments": [
            {"id": 0, "start": 0.0, "end": 1.2, "text": "Um..."},
            {"id": 1, "start": 1.5, "end": 3.8, "text": "Today we are..."},
            {"id": 2, "start": 4.0, "end": 9.2, "text": "Today we are announcing the autonomous video engine."},
            {"id": 3, "start": 9.5, "end": 10.8, "text": "Um yeah."},
            {"id": 4, "start": 11.0, "end": 16.5, "text": "It runs 100% locally on your machine with zero cloud costs."}
        ]
    }

    plan = director.direct(mock_transcript)
    assert isinstance(plan, DirectorPlan)
    assert len(plan.edit_decision_list) == 5

    # Segment 0 ("Um...") should be pruned as filler
    assert plan.edit_decision_list[0].keep is False

    # Segment 1 ("Today we are...") should be pruned as false start
    assert plan.edit_decision_list[1].keep is False

    # Segment 2 (Clean final take) should be kept
    assert plan.edit_decision_list[2].keep is True

    # Segment 4 should be kept
    assert plan.edit_decision_list[4].keep is True

    assert plan.removed_takes_count >= 2
    assert plan.estimated_duration > 0
    assert len(plan.visual_cues) > 0
