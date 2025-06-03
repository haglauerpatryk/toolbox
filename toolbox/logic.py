_logic_hook_registry = {}

def logic_rule(name):
    def decorator(func):
        _logic_hook_registry[name] = func
        return func
    return decorator


class LogicResolver:
    def __init__(self, variables):
        self.variables = variables

    def resolve_logic_block(self, block: dict):
        """
        Expects:
        {
            "always": [...],
            "if_var": { "DEBUG": [...] },
            "if_not_var": { "DEBUG": [...] }
        }
        Returns a flat list of resolved hook names.
        """
        results = []

        for rule_name, payload in block.items():
            handler = _logic_hook_registry.get(rule_name)
            if handler:
                results.extend(handler(self, payload))

        return results

    @logic_rule("always")
    def _always(self, payload):
        return list(payload) if isinstance(payload, list) else []

    @logic_rule("if_var")
    def _if_var(self, payload):
        resolved = []
        for var, hooks in payload.items():
            if self.variables.get(var):
                resolved.extend(hooks)
        return resolved

    @logic_rule("if_not_var")
    def _if_not_var(self, payload):
        resolved = []
        for var, hooks in payload.items():
            if not self.variables.get(var):
                resolved.extend(hooks)
        return resolved
