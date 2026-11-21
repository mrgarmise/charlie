"""Development extension of the existing Learning Executive."""

from memory.learning_projects import LearningExecutive


class SandboxLearningExecutive(LearningExecutive):
    """Add opt-in sandbox organization methods to the existing Executive."""

    def commission_sandbox_organization(self, factory, mission, goal, assignments, **limits):
        """Commission a development organization without runtime or actuator authority."""
        return factory.commission(mission, goal, assignments, **limits)

    def select_sandbox_organization(self, factory, mission, goal, context, templates, *, frozen=False):
        """Use evaluated sandbox outcomes to choose among permitted organizations."""
        try:
            retained = factory.inspect(mission)
        except KeyError:
            retained = None
        if retained is not None:
            template = retained.get("template")
            if (retained["goal"] != goal or retained.get("context") != context
                    or template not in templates
                    or retained["nodes"] != factory.describe(factory.validate(templates[template]))):
                raise ValueError("mission identity already bound to another selection")
            return retained["decision"]
        decision = factory.rank(context, templates, frozen=frozen)
        if not decision:
            raise ValueError("no available organization templates")
        selected = decision[0]["template"]
        self.commission_sandbox_organization(
            factory, mission, goal, templates[selected], context=context, template=selected,
            decision=decision)
        return decision
