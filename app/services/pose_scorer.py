"""AIチームの接続点。未接続を検出失敗や架空の得点として扱わない。"""
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class ScoreResult:
    status: str  # success / undetected / unavailable
    score: float | None = None

class PoseScorer(Protocol):
    def evaluate(self, image_bytes: bytes, reference_id: str) -> ScoreResult: ...

class PendingPoseScorer:
    def evaluate(self, image_bytes: bytes, reference_id: str) -> ScoreResult:
        return ScoreResult('unavailable')

class DemoPoseScorer:
    """通信フロー専用。AI評価ではない。両者75点で固定。"""
    def evaluate(self, image_bytes: bytes, reference_id: str) -> ScoreResult:
        return ScoreResult('success', 75.0)
