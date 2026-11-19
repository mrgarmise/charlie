"""Accept optional human/LLM hypotheses as bounded text. Only a fixed catalog executes."""

from dataclasses import asdict, dataclass
from ..inquiry import Question, choose


@dataclass(frozen=True)
class ExperimentProposal:
    objective: str
    prediction: str
    epistemic_status: str
    command_timeline: tuple
    hardware_accepted: bool = False
    authorization: str = "separate operator approval pending"
    version: int = 1


def propose(hypothesis=None):
    if hypothesis is not None and (
        type(hypothesis) is not str or not 1 <= len(hypothesis) <= 500
    ):
        raise ValueError("a single short explanation is required")
    catalog = [
        Question(
            "stationary-board",
            "vision",
            "experimental",
            "Can a fixed board explain the image shift?",
            True,
            0.9,
            0.1,
        ),
        Question(
            "second-view",
            "vision",
            "experimental",
            "Would a measured second view resolve the depth ambiguity?",
            True,
            0.8,
            0.3,
        ),
    ]
    best = choose(catalog)
    output = asdict(
        ExperimentProposal(
            best.statement,
            "stationary reference remains fixed within calibration uncertainty",
            "proposed",
            (),
        )
    )
    output.update(
        hypothesis=hypothesis,
        alternatives=["camera displacement", "servo mapping", "latency"],
        required_envelope="fixed external camera, unpowered stationary body",
        ranked_questions=[best.key] + [q.key for q in catalog if q != best],
    )
    return output
