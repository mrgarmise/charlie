#!/usr/bin/env python3
"""Run implemented software-boundary checks; does not certify hardware safety."""
import subprocess
import sys

TESTS = [
    'tests/test_unified_reconciliation.py',
    'tests/test_shared_mobile_executor.py',
    'tests/test_unified_actuator_requests.py',
    'tests/test_actuator_authority.py',
    'tests/test_rp2040_gateway_fence.py',
    'tests/test_normal_multi_ability.py',
    'tests/test_legacy_motion_boundary.py',
    'tests/test_camera_sources.py',
    'tests/test_sensory_history.py',
    'tests/test_pet_completion.py::test_uncertain_stop_latches_executor_and_prevents_next_start',
    'tests/test_pet_completion.py::test_uncertain_stop_is_not_cleared_by_later_acknowledgement',
    'tests/test_pet_completion.py::test_ambiguous_start_exception_latches_even_if_later_stop_acks',
]

if __name__ == '__main__':
    raise SystemExit(subprocess.call([sys.executable, '-m', 'pytest', '-q', *TESTS]))
