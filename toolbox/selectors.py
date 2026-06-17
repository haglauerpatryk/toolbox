from toolbox.registries import rule


class Selector:
    def __init__(self, variables):
        self.variables = variables

    def resolve(self, block):
        results = []
        for rule_name, payload in (block or {}).items():
            results.extend(rule.get(rule_name).func(self.variables, payload))
        return results


@rule.register("always")
def _always(variables, payload):
    return list(payload or [])


@rule.register("if_var")
def _if_var(variables, payload):
    resolved = []
    for var, names in (payload or {}).items():
        if variables.get(var):
            resolved.extend(names)
    return resolved


@rule.register("if_not_var")
def _if_not_var(variables, payload):
    resolved = []
    for var, names in (payload or {}).items():
        if not variables.get(var):
            resolved.extend(names)
    return resolved
