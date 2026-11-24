"""Development extension of the existing Learning Executive."""

from memory.learning_projects import LearningExecutive


class SandboxLearningExecutive(LearningExecutive):
    """Add opt-in sandbox organization methods to the existing Executive."""

    def commission_sandbox_organization(self, factory, mission, goal, assignments, **limits):
        """Commission a development organization without runtime or actuator authority."""
        return factory.commission(mission, goal, assignments, **limits)

    def select_sandbox_organization(self, factory, mission, goal, context, templates, *, frozen=False, work_budget=None):
        """Use evaluated sandbox outcomes to choose among permitted organizations."""
        try:
            retained = factory.inspect(mission)
        except KeyError:
            retained = None
        if retained is not None:
            template = retained.get("template")
            if (retained["goal"] != goal or retained.get("context") != context
                    or retained.get("work_budget") != work_budget
                    or template not in templates
                    or retained.get("initial_nodes", retained["nodes"]) != factory.describe(factory.validate(templates[template]))):
                raise ValueError("mission identity already bound to another selection")
            return retained["decision"]
        decision = factory.rank(context, templates, frozen=frozen)
        if not decision:
            raise ValueError("no available organization templates")
        selected = decision[0]["template"]
        self.commission_sandbox_organization(
            factory, mission, goal, templates[selected], context=context, template=selected,
            decision=decision, work_budget=work_budget)
        return decision

    def retain_sandbox_outcome(self, factory, mission):
        """Retain a stable, source-linked terminal outcome in the evidence journal."""
        view = factory.inspect(mission)
        if view["state"] not in {"completed", "failed", "cancelled", "expired"}:
            return None
        episode = f"sandbox-organization:{mission}"
        references = {}
        with self.journal.batch():
            for assignment in view["nodes"]:
                task = view["tasks"][assignment["name"]]
                item = task["evidence"]
                if item is None:
                    continue
                payload = item["payload"]
                sources = [references[digest] for digest in payload["inputs"].values()]
                record = self.journal.append(
                    "observation", payload, episode=episode, sources=sources,
                    producer=assignment["capability"], version=assignment["version"],
                    provenance={"sandbox_digest": item["digest"]})
                references[item["digest"]] = record.id
            return self.journal.append(
                "event", dict(category="sandbox_organization_outcome",
                              goal=view["goal"], state=view["state"], decision=view.get("decision")),
                episode=episode, sources=references.values(),
                producer="LearningExecutive", version="sandbox-organization-v1")
