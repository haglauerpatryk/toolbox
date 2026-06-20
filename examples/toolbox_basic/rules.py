import os

from toolbox import rule

# Custom selector rules, registered exactly like the core ones. They extend the
# config grammar without touching the core's always/if_var/if_not_var.


@rule.register("if_env")
def if_env(variables, payload):
    """Include names when an environment variable is set and truthy."""
    resolved = []
    for env_name, names in (payload or {}).items():
        if os.environ.get(env_name):
            resolved.extend(names)
    return resolved


@rule.register("if_equals")
def if_equals(variables, payload):
    """Value-based selection: {VAR: {expected_value: [names]}}."""
    resolved = []
    for var, value_map in (payload or {}).items():
        actual = variables.get(var)
        for expected, names in (value_map or {}).items():
            if str(actual) == str(expected):
                resolved.extend(names)
    return resolved
