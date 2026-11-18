"""Run research tests with Python socket operations denied."""

import sys

import pytest


def deny_sockets(event, arguments):
    if event.startswith("socket."):
        raise RuntimeError(f"offline test denied {event}")


def main():
    sys.addaudithook(deny_sockets)
    return pytest.main(["-q", "research/uel"])


if __name__ == "__main__":
    raise SystemExit(main())
