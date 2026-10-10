"""A safe, dry-run controller. No hardware or RetroArch calls."""

from .models import Action
from .controller_sandbox import validate_controls


class DryRunController:
    def execute(self, action: Action) -> Action:
        validate_controls(action.controls)
        return action
