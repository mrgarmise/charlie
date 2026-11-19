"""Self-contained, offline review of a qualification. Nothing in this view executes a skill."""

import base64
import html
from .qualification import read_object


def render_review(folder, qualification):
    report = read_object(folder, qualification)
    candidate = read_object(folder, report["candidate"])
    rows = "".join(
        f'<tr><td>{html.escape(r["family"])}</td><td>{r["seed"]}</td>'
        f'<td>{r["fixed"]:.3f}</td><td>{r["fitted"]:.3f}</td></tr>'
        for r in report["withheld"]
    )
    image = base64.b64encode((folder / "overlay.png").read_bytes()).decode()
    return f"""<!doctype html><meta charset=utf-8><title>Visual twin review</title>
    <main style="font:18px system-ui;max-width:48rem;margin:3rem auto;color:#172527">
    <h1>Visual twin review</h1><p>Simulation validation: {report["passed"]}. Hardware approval pending.</p>
    <p>Fitted delay in ticks: {candidate["plausible"]}. Qualification <code>{qualification}</code></p>
    <table cellpadding=6><caption>Held-out marker error (RMS pixels)</caption><thead><tr>
    <th>Motion</th><th>Seed</th><th>Baseline</th><th>Candidate</th></tr></thead><tbody>{rows}</tbody></table>
    <figure><img src="data:image/png;base64,{image}" width="480" alt="Predicted and measured pixel trajectories">
    <figcaption>Predicted rings and observed dots from the held-out trajectory.</figcaption></figure></main>"""
