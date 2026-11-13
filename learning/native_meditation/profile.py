"""Explicit opt-in composition of the existing Executive; never a second chooser."""
import os
from pathlib import Path
from memory.evidence import EvidenceJournal
from learning.question_selection import QuestionQueue
from learning.meditation_consultation import MeditationConsultations
from .client import NativeBackend
from .coordinator import NativeMeditationCoordinator


def attach(lifecycle):
    backend=NativeBackend();config=backend.call('configuration')
    sources=config['question_sources'];path=Path(config['answer_journal'])
    if not sources or len(sources)>16:raise ValueError('protected explicit source inventory required')
    # Reject aliases before opening any writable notebook.
    for source in sources:
        if path.resolve()==Path(source).resolve() or (path.exists() and Path(source).exists() and os.path.samefile(path,source)):
            raise ValueError('decision notebook aliases original evidence')
    journal=EvidenceJournal(path)
    try:
        consultation=MeditationConsultations(QuestionQueue(journal),sources,enabled=True,
            daily_limit=config['daily_limit'],cooldown=config['cooldown'],slot_seconds=config['max_seconds'])
        lifecycle.meditation_consultations=NativeMeditationCoordinator(consultation,backend)
        lifecycle.native_decision_journal=journal
    except BaseException:journal.close();raise
