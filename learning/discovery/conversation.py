"""Deterministic text adapter over committed notebook records."""

import re
from .journal import identifier, plain


def _describe(row):
    sentence = f"{row['date'][:10]} · {row['question_id']} · {row['question']} ({row['status']})"
    if row["findings"]:
        sentence += " " + " ".join(row["findings"][:2])
    if row["uncertainty"]:
        sentence += " Open issue: " + row["uncertainty"][0]
    if row["citations"]:
        sentence += " Local sources: " + ", ".join(row["citations"])
    if row["corrections"]:
        sentence += " Owner correction: " + row["corrections"][0]["note"]
    return sentence


def respond(journal, text, *, now=None, owner=False, question_id=None, session_id=None):
    """The trusted local adapter supplies owner identity independently of request text."""
    text = plain(text, 800)
    lower = text.casefold().strip(" ?.")
    if question_id:
        identifier(question_id)
    if session_id:
        identifier(session_id)
    keep = re.fullmatch(r"keep thinking about\s+(.+)", text, re.I)
    intent = "recent"
    topic = None
    if keep:
        intent = "queue"
    elif lower in {"what have you learned", "what did the researcher find", "what disagreed",
                   "what can we do with it", "what is left to investigate"}:
        intent = "collaborative"
    elif "changed your mind" in lower or "correction" in lower:
        intent = "changes"
    elif "evidence" in lower or "show details" in lower:
        intent = "evidence"
    elif "stuck" in lower or "blocked" in lower:
        intent = "blocked"
    elif "why did you choose" in lower:
        intent = "choice"
    elif "investigate next" in lower or "next question" in lower:
        intent = "next"
    elif "actually investigated" in lower or "in your queue" in lower:
        intent = "state"
    else:
        match = re.search(r"(?:discover|learn|investigate|conclude)(?:ed)? about (.+?)[?.]*$",lower)
        if match:
            intent = "topic"
            topic = match.group(1)
            # Include singular and plural forms for a topical lookup.
            if len(topic) > 4 and topic.endswith("s"):
                topic = topic[:-1]
        elif not any(word in lower for word in ("lately", "this week", "recent", "pondering", "thinking")):
            intent = "help"
    if keep:
        qid = journal.queue(keep.group(1), owner=owner, now=now)
    if intent == "state" and question_id is None and session_id is None:
        # Pure text clients can identify a known question by its exact ID.
        for token in re.findall(r"[A-Za-z0-9_-]+",text):
            row = journal.db.execute("SELECT id FROM questions WHERE lower(id)=lower(?)",(token,)).fetchone()
            if row:
                question_id = row[0]
                break
    recent = intent == "recent"
    digest = journal.digest(now,topic=topic,question_id=question_id,session_id=session_id,
                            all_time=not recent)
    rows = digest["completed_sessions"]
    current = rows[0] if rows else None
    next_q = journal.select(now)
    interval = digest["time_window"]
    messages = []
    if intent == "queue":
        messages.append(f"Queued for owner-directed inquiry: {qid}.")
    elif intent == "collaborative":
        selected = next((journal.session(row["id"]) for row in rows
                         if journal.session(row["id"])["record"].get("collaborative")), None)
        if selected is None:
            messages.append("There is no matching committed collaborative meditation.")
        else:
            record = selected["record"]
            detail = record["collaborative"]
            turns = {turn["payload"]["task"]: turn["payload"]["result"] for turn in detail["turns"]}
            messages.append(f"Recorded session {selected['id']} · {detail['stop_reason']}.")
            if lower == "what did the researcher find":
                for source in turns["researcher"]["sources"]:
                    messages.append(f"{source['id']} ({source['locator']}): {source['excerpt']}")
                if not turns["researcher"]["sources"]:
                    messages.append("The Researcher retained no source excerpts.")
            elif lower == "what disagreed":
                conflicts = detail["evaluation"]["conflicts"]
                messages.append("Conflicting sources: " + ", ".join(conflicts) if conflicts
                                else "There were no confirmed source conflicts in this session.")
            elif lower == "what can we do with it":
                actions = turns["implementer"]["actions"]
                messages.extend(f"{horizon} · proposal only · {action}" for horizon, action in actions.items())
                if not actions:
                    messages.append("The session recorded no specific application proposals.")
            elif lower == "what is left to investigate":
                messages.extend(record["followups"])
            else:
                messages.extend(record["findings"])
    elif intent == "changes":
        for row in rows:
            for correction in row["corrections"]:
                messages.append(f"{correction['at'][:10]} · {row['question_id']} · Owner correction: {correction['note']}")
            if row["status"] == "contradicted":
                messages.append(_describe(row))
        if not messages:
            messages.append("I found no recorded correction or contradicted conclusion in the displayed records.")
    elif intent == "blocked":
        messages.extend(f"{b['id']} · {b['reason']}" for b in digest["blockers"][:5])
        if not messages:
            messages.append("No blocker is recorded in the matching attempts.")
    elif intent == "next":
        messages.append(f"{next_q['id']} · {next_q['question']} Selection factors: {next_q['selection_reason']}."
                        if next_q else "There is no eligible queued question.")
    elif intent == "choice":
        if current:
            messages.append(f"{current['question_id']} · {current['question']} Recorded selection factors: {current['selection_reason']}.")
        else:
            messages.append("There is no matching completed selection to explain.")
    elif intent == "evidence":
        if current:
            messages.append(_describe(current))
            for check in current["checks"]:
                messages.append("Check: " + str(check.get("detail",check.get("tool","recorded check"))))
            messages.append(f"Committed session: {current['id']}.")
        else:
            messages.append("There is no matching committed conclusion with evidence.")
    elif intent == "state":
        if not question_id and not session_id:
            messages.append("Specify a question ID to distinguish its queue entry from its recorded attempts.")
        elif current:
            messages.append("Completed a recorded inquiry. " + _describe(current))
        elif digest["attempted_question_ids"]:
            messages.append("An attempt is recorded. It has no committed conclusion.")
        elif question_id and journal.db.execute("SELECT id FROM questions WHERE id=?",(question_id,)).fetchone():
            messages.append(f"{question_id} is queued with no recorded attempt.")
        else:
            messages.append("No matching question or session was found.")
    elif intent == "help":
        messages.append("Ask about recent meditations, a topic, evidence, blockers, corrections or the next question.")
    else:
        if recent:
            messages.append(f"Recorded meditations from {interval['start']} through {interval['end']}.")
        if rows:
            messages.extend(_describe(row) for row in rows[:5])
        elif topic:
            messages.append(f"No committed meditation matches the topic “{topic}”.")
        else:
            messages.append("I haven't completed any recorded meditations in that period.")
            if next_q:
                messages.append(f"Next queued question: {next_q['id']} · {next_q['question']}")
    if digest["truncated"]:
        messages.append("Showing records from the most recent 100 matching attempts.")
    return dict(schema="DiscoveryConversation/v1",intent=intent,text="\n".join(messages),
                digest=digest,next_question=next_q and {k:next_q[k] for k in ("id","question","selection_reason")})
