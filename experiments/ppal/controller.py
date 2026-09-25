"""A safe, dry-run controller. No hardware or RetroArch calls."""

from .models import Action


class DryRunController:
    def execute(self, action: Action) -> Action:
        return action
