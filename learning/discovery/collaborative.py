"""Trusted, offline research roles for the development Agent Factory."""

from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import re

from learning.agent_factory import Assignment, Capability, check_worker_lease, encode
from .inquiry import formal_check
from .journal import plain


SCHEMA = "CollaborativeResearch/v1"
VERSION = "offline-research-v1"
ROLES = ("inventor", "archivist", "scientist", "researcher", "implementer")
WORKERS = (*ROLES, "prior-art-review", "review", "brief")


@dataclass(frozen=True)
class Study:
    question: str
    reference_query: str
    sources: tuple[str, ...]
    label: str
    units: str
    applications: tuple[str, str, str]
    next_question: str


STUDIES = (
    Study(
        "How much energy in joules does one electron gain across one volt?",
        "electron volt hertz relationship",
        ("CODATA22-L113", "CODATA22-L118"),
        "electron volt", "J",
        ("Check the eV-to-J conversion in a sample calculation.",
         "Add a unit conversion check to a spectroscopy data pipeline and compare it with an independent library.",
         "Preserve unit definitions, calibration records and cross-laboratory comparisons with archived spectra."),
        "How does uncertainty in the accelerating voltage propagate into an electron energy estimate?",
    ),
    Study(
        "How far does light travel in vacuum in one microsecond?",
        "electron volt hertz relationship speed of light vacuum",
        ("CODATA22-L319",),
        "speed of light in vacuum", "m s^-1",
        ("Check whether a 300 m per microsecond planning estimate is adequate.",
         "Compare one-way timing and two-way ranging in a documented link budget.",
         "Maintain traceable clock and propagation-delay calibration procedures for distributed infrastructure."),
        "How do refractive index and two-way travel affect the delay of a fiber link?",
    ),
)
STUDY_BY_QUESTION = {study.question: study for study in STUDIES}


def derive(question):
    study = STUDY_BY_QUESTION.get(question)
    if study == STUDIES[0]:
        value = Fraction("1.602176634e-19") * 1
        return dict(tool="rational_arithmetic", valid=True, value=str(value),
                    detail="Assuming the SI elementary charge 1.602176634e-19 C and 1 V, qV = 1.602176634e-19 J.")
    if study == STUDIES[1]:
        value = Fraction(299792458) * Fraction("0.000001")
        return dict(**formal_check("What is 299792458 * 0.000001?"), value=str(value))
    return formal_check(question) or dict(tool="none", valid=False,
                                        detail="No validated derivation is available for this question.")


def message(kind, **fields):
    check_worker_lease()
    return dict(schema=SCHEMA, kind=kind, **fields)


def result(inputs, sender, kind):
    item = inputs[sender]
    envelope = item["payload"]
    if (item["digest"] != sha256(encode(envelope).encode()).hexdigest()
            or envelope["task"] != sender or envelope["capability"] not in
            (("meditation-broad", "meditation-scoped") if sender == "supervisor" else (sender,))):
        raise ValueError("research evidence sender or digest mismatch")
    data = envelope["result"]
    if data.get("schema") != SCHEMA or data.get("kind") != kind:
        raise ValueError("unexpected research evidence")
    return data


def supervisor(strategy):
    def commission(question, _):
        study = STUDY_BY_QUESTION.get(question)
        assignments = (
            ("inventor", ()),
            ("archivist", ("inventor",)),
            ("scientist", ("inventor", "archivist")),
            ("researcher", ("scientist", "archivist")),
            ("implementer", ("researcher", "scientist")),
            ("review", ("researcher", "scientist", "implementer")),
        )
        closing_dependencies = (*ROLES, "review")
        if strategy == "scoped" and study:
            assignments += (("prior-art-review", ("researcher",)),)
            closing_dependencies += ("prior-art-review",)
        assignments += (("brief", closing_dependencies),)
        plan = [dict(name=name, capability=name, depends_on=list(dependencies))
                for name, dependencies in assignments]
        return message("QUESTION", strategy=strategy, question=question,
                       agenda=list(ROLES), staged_source=bool(study),
                       organization_proposal=encode(dict(schema=1, assignments=plan)))
    return commission


def templates():
    return {strategy: (Assignment("supervisor", f"meditation-{strategy}"),)
            for strategy in ("broad", "scoped")}


def inventor(question, inputs):
    study = STUDY_BY_QUESTION.get(question)
    result(inputs, "supervisor", "QUESTION")
    return message("PRIOR_ART_REQUEST", status="hypothesized",
                   proposal=f"Test a dimensional model for: {question}",
                   search=study.reference_query if study else question,
                   novelty="unchecked", recipient="archivist")


def archivist(question, inputs):
    proposal = result(inputs, "inventor", "PRIOR_ART_REQUEST")
    return message("PRIOR_ART_REQUEST", search=proposal["search"],
                   limits="Search the pinned local archive after the derivation. Preserve excerpt lineage.",
                   recipient="scientist")


def scientist(question, inputs):
    request = result(inputs, "archivist", "PRIOR_ART_REQUEST")
    result(inputs, "inventor", "PRIOR_ART_REQUEST")
    check = derive(question)
    return message("CHALLENGE", status="derived" if check["valid"] else "inconclusive",
                   check=check, search=request["search"], recipient="researcher",
                   limitation="The calculation is conditional on the stated inputs and idealized conditions.")


def researcher(archive, provenance):
    def retrieve(question, inputs):
        result(inputs, "scientist", "CHALLENGE")
        request = result(inputs, "archivist", "PRIOR_ART_REQUEST")
        plan = result(inputs, "supervisor", "QUESTION")
        study = STUDY_BY_QUESTION.get(question)
        if plan["strategy"] == "scoped" and study:
            documents = [archive.get(source_id) for source_id in study.sources]
        else:
            documents = archive.retrieve(request["search"], limit=1, budget=400)
        sources = []
        for doc in documents:
            if not doc:
                continue
            check_worker_lease()
            excerpt = doc["text"].encode()[:480].decode(errors="ignore")
            sources.append(dict(
                id=doc["id"], excerpt=excerpt, sha256=doc["sha256"],
                excerpt_sha256=sha256(excerpt.encode()).hexdigest(),
                locator=doc["locator"], metadata=provenance.get(doc["source"], {}),
                access="offline archive", truncated=bool(doc.get("truncated") or excerpt != doc["text"]),
                treatment="untrusted quotation"))
        return message("SOURCE_FINDING", status="imported" if sources else "inconclusive",
                       sources=sources, recipient="implementer")
    return retrieve


def implementer(question, inputs):
    observation = result(inputs, "researcher", "SOURCE_FINDING")
    challenge = result(inputs, "scientist", "CHALLENGE")
    study = STUDY_BY_QUESTION.get(question)
    actions = dict(zip(("2 minutes", "2 years", "2 decades"), study.applications)) if study else {}
    return message("FEASIBILITY_REVIEW", authority="proposal-only", checked=challenge["check"]["valid"],
                   available_sources=len(observation["sources"]), actions=actions,
                   alternatives=["Use the exact equation with independently measured inputs.",
                                 "Use a documented planning approximation and bound its error."],
                   constraint="Review input units and uncertainty before relying on any estimate.",
                   recipient="review")


def comparable(study, source):
    if source["truncated"] or not source["metadata"] or source["id"] not in study.sources:
        return None
    excerpt = source["excerpt"]
    label = "electron volt-joule relationship" if source["id"] == "CODATA22-L118" else study.label
    match = re.fullmatch(re.escape(label) + r" ([\d .e+-]+) \(exact\) " + re.escape(study.units), excerpt)
    if match is None or "..." in match[1]:
        return None
    value = Fraction(match[1].replace(" ", ""))
    return value / 1_000_000 if study.units == "m s^-1" else value


def review(question, inputs):
    sources = result(inputs, "researcher", "SOURCE_FINDING")["sources"]
    check = result(inputs, "scientist", "CHALLENGE")["check"]
    result(inputs, "implementer", "FEASIBILITY_REVIEW")
    study = STUDY_BY_QUESTION.get(question)
    observations = []
    if study and check["valid"]:
        for source in sources:
            value = comparable(study, source)
            if value is not None:
                observations.append(dict(id=source["id"], normalized_value=str(value),
                                         agrees=value == Fraction(check["value"])))
    conflicts = [item["id"] for item in observations if not item["agrees"]]
    status = "contradicted" if conflicts else "reconciled" if observations else "inconclusive"
    return message("CONTRADICTION" if conflicts else "CLAIM", status=status,
                   comparisons=observations, conflicts=conflicts,
                   organization_score=float(status == "reconciled"),
                   evaluation_case=sha256(question.encode()).hexdigest(),
                   recipient="brief")


def prior_art_review(question, inputs):
    sources = result(inputs, "researcher", "SOURCE_FINDING")["sources"]
    origins = {source["metadata"].get("url") for source in sources} - {None}
    return message("PRIOR_ART_REVIEW", exact_scope_rows=[source["id"] for source in sources],
                   distinct_origins=len(origins), novelty="unchecked beyond the pinned archive",
                   recipient="brief")


def brief(question, inputs):
    review_kind = inputs["review"]["payload"]["result"]["kind"]
    if review_kind not in {"CLAIM", "CONTRADICTION"}:
        raise ValueError("unexpected evaluator message")
    assessment = result(inputs, "review", review_kind)
    study = STUDY_BY_QUESTION.get(question)
    if assessment["status"] == "reconciled" and study:
        followup = study.next_question
    elif assessment["status"] == "contradicted":
        followup = f"Can an independently published reference resolve this disagreement? {question}"
    else:
        followup = f"Which available source directly addresses this question? {question}"
    prior_art = (result(inputs, "prior-art-review", "PRIOR_ART_REVIEW")
                 if "prior-art-review" in inputs else None)
    return message("SUMMARY", prior_art=prior_art, assessment=assessment["status"], next_question=plain(followup),
                   stop_reason="completed" if assessment["status"] == "reconciled" else
                   "conflict unresolved" if assessment["conflicts"] else "new evidence needed",
                   recipient="discovery-journal")


def capabilities(archive, provenance):
    return (
        Capability("meditation-broad", VERSION, "supervisor", supervisor("broad"), WORKERS),
        Capability("meditation-scoped", VERSION, "supervisor", supervisor("scoped"), WORKERS),
        Capability("inventor", VERSION, "worker", inventor),
        Capability("archivist", VERSION, "worker", archivist),
        Capability("scientist", VERSION, "worker", scientist),
        Capability("researcher", VERSION, "worker", researcher(archive, provenance)),
        Capability("implementer", VERSION, "worker", implementer),
        Capability("prior-art-review", VERSION, "worker", prior_art_review),
        Capability("review", VERSION, "evaluator", review),
        Capability("brief", VERSION, "worker", brief),
    )
