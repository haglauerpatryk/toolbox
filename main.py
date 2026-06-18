import time

from examples.toolbox_basic import catch
from my_toolbox import error_toolbox


@error_toolbox
def do_something(name):
    time.sleep(0.2)
    print(f"Doing something with {name}")
    return f"Processed {name}"


# a single freeform lambda
@error_toolbox(on_error=lambda e: f"<recovered from {type(e).__name__}>")
def swallow_with_fallback():
    raise ValueError("Oops!")


# routing by exception type — catch() resolves the map into one lambda
@error_toolbox(on_error=catch({
    ValueError: lambda e: "<bad input>",                     # swallow with fallback
    KeyError:   lambda e: e,                                 # re-raise the original
    Exception:  lambda e: RuntimeError(f"unexpected: {e}"),  # translate everything else
}))
def routed(fail_with):
    raise fail_with


if __name__ == "__main__":
    print("do_something ->", do_something("test-file.txt"))
    print("swallow_with_fallback ->", swallow_with_fallback())

    print("routed(ValueError) ->", routed(ValueError("bad")))

    try:
        routed(KeyError("missing"))
    except Exception as e:
        print(f"routed(KeyError) propagated -> {type(e).__name__}: {e}")

    try:
        routed(ZeroDivisionError("/0"))
    except Exception as e:
        print(
            f"routed(ZeroDivisionError) propagated -> {type(e).__name__}: {e} "
            f"(cause: {type(e.__cause__).__name__})"
        )
