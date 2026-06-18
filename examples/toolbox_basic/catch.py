def catch(handlers):
    def dispatch(e):
        for exc_type in type(e).__mro__:
            for key, handler in handlers.items():
                if key is exc_type or (isinstance(key, tuple) and exc_type in key):
                    return handler(e)
        return e

    return dispatch
