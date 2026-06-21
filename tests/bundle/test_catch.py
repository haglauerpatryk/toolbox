from examples.toolbox_basic import catch


def test_exact_type_matches():
    dispatch = catch({ValueError: lambda e: "v"})
    assert dispatch(ValueError("x")) == "v"


def test_unmatched_returns_the_exception():
    # the contract: returning the exception is how the framework re-raises it
    dispatch = catch({KeyError: lambda e: "k"})
    err = ValueError("x")
    assert dispatch(err) is err


def test_exception_is_catch_all():
    dispatch = catch({Exception: lambda e: "any"})
    assert dispatch(KeyError("x")) == "any"
    assert dispatch(ValueError("x")) == "any"


def test_most_specific_wins_regardless_of_map_order():
    dispatch = catch(
        {
            Exception: lambda e: "broad",
            ValueError: lambda e: "specific",
        }
    )
    assert dispatch(ValueError("x")) == "specific"


def test_subclass_routes_to_registered_parent():
    class MyError(ValueError):
        pass

    dispatch = catch({ValueError: lambda e: "v"})
    assert dispatch(MyError("x")) == "v"


def test_tuple_key_groups_types():
    dispatch = catch({(KeyError, ValueError): lambda e: "grouped"})
    assert dispatch(KeyError("x")) == "grouped"
    assert dispatch(ValueError("x")) == "grouped"


def test_handler_receives_the_exception():
    seen = []
    dispatch = catch({ValueError: lambda e: seen.append(e) or "done"})
    err = ValueError("x")
    assert dispatch(err) == "done"
    assert seen == [err]


def test_handler_return_value_is_passed_through():
    # catch only selects; it does not change the on_error return contract
    err = ValueError("x")
    dispatch = catch({ValueError: lambda e: e})
    assert dispatch(err) is err

    dispatch = catch({ValueError: lambda e: {"ok": False}})
    assert dispatch(err) == {"ok": False}
