from examples.scenarios import platform as P


def before(tb):
    return [f.__name__ for f in tb.hooks["before"]]


def sink_names(tb):
    return [s.__name__ for s in tb.sinks]


def test_both_services_inherit_base_diagnostics():
    # track_info + count_calls + the memory sink come from PlatformBase
    assert before(P.payments_svc)[:2] == ["track_info", "count_calls"]
    assert "track_info" in before(P.llm_svc)
    assert "count_calls" in before(P.llm_svc)
    assert "memory" in sink_names(P.payments_svc)
    assert "memory" in sink_names(P.llm_svc)


def test_services_add_their_own_pieces():
    assert "json_lines" in sink_names(P.payments_svc)
    assert "handle_problem" in [f.__name__ for f in P.payments_svc.hooks["on_error"]]
    assert "capture_args" in before(P.llm_svc)
    assert len(P.llm_svc.wrappers) == 3  # rate_limit, retry, validate


def test_payments_overlap_with_base_is_deduped_with_warning(capsys):
    tb = P.PaymentsService()  # fresh construction to capture the warning
    err = capsys.readouterr().err
    assert "removed duplicate hook" in err
    assert "count_calls" in err
    assert before(tb).count("count_calls") == 1  # collapsed to one


def test_llm_service_has_no_overlap_and_stays_quiet(capsys):
    P.LLMService()
    assert capsys.readouterr().err == ""


def test_inherited_payments_charge_routes(monkeypatch, tmp_path):
    monkeypatch.setattr(P.payments_svc, "log_directory", str(tmp_path))
    assert P.charge(1000, "4242424242424242")["status"] == "captured"
    assert P.charge(-1, "4242424242424242")["status"] == "rejected"


def test_inherited_llm_ask_self_heals(monkeypatch, tmp_path, instant_retry):
    monkeypatch.setattr(P.llm_svc, "log_directory", str(tmp_path))
    out = P.ask("platform-q")
    assert out["confidence"] == 0.92
