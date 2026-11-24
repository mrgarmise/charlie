"""Opt-in entry into Charlie's existing bounded development turn scheduler."""

from learning.lifecycle import DevelopmentLifecycle, run
from learning.sandbox_events import LifecyclePublication
from learning.sandbox_executive import SandboxLearningExecutive
from stimulus.bus import StimulusBus


class ScheduledExecutive(SandboxLearningExecutive):
    def __init__(self, journal, gateway, factory, mission):
        super().__init__(journal, gateway)
        self.factory, self.mission = factory, mission

    def develop(self, lifecycle):
        view = self.factory.inspect(self.mission)
        if view["state"] in {"queued", "running"}:
            try:
                progressed = self.factory.step(self.mission, guard=lifecycle.yield_for_primary)
            except InterruptedError:
                if self.factory.inspect(self.mission)["state"] not in {"paused", "cancelled", "expired"}:
                    raise
                progressed = False
        else:
            progressed = False
        lifecycle.publication.flush()
        terminal = self.retain_sandbox_outcome(self.factory, self.mission)
        lifecycle.last_turn = {"progress_occurred": progressed, "reason": "organization turn"}
        if terminal is not None or self.factory.inspect(self.mission)["state"] == "paused":
            lifecycle.done = True


def run_organization(database, factory, mission, commission):
    """Run the default developmental scheduler against an isolated notebook."""
    if database.name != "learning-evidence.sqlite3":
        raise ValueError("scheduled missions require a development learning-evidence.sqlite3 path")

    class OrganizationLifecycle(DevelopmentLifecycle):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.executive = ScheduledExecutive(self.journal, self.gateway, factory, mission)
            self.done = False
            commission(self.executive)
            self.publication = LifecyclePublication(StimulusBus(), factory, mission)
            self.publication.__enter__()
            self.publication.flush()

        def turn(self):
            if self.done:
                self.last_turn = {"progress_occurred": False, "reason": "organization retired"}
                return False
            return super().turn()

        def close(self):
            try:
                self.publication.__exit__(None, None, None)
            finally:
                super().close()

    return run(database.parent, (), turns=14, interval=.05, wall_seconds=60,
               lifecycle_factory=OrganizationLifecycle)
