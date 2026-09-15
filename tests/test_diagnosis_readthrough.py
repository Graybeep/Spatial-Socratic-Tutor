"""§9.5's instrument, tested on the parts that do not need a key.

`collect()` needs a real model by design - reading thirty mock diagnoses
measures `mock_tutor.py`'s template - so what is tested here is everything
around it: the refusal that keeps a mock run from being mistaken for §9.5, the
response encoding that lets a student answer honestly, and the scoring, which is
where a well-formed number over nothing would be born.
"""
from __future__ import annotations

import pytest

from eval import diagnosis_readthrough as RT
from server.config import CONFIG
from server.graph_store import GraphStore


def _field(**kw):
    base = dict(n=1, item_id="itm_0001", item_type="node_click", node_label="Flow",
                turn=1, hint_level=1, lit=52, condition="zero",
                student_pick="flow_control", pick_correct=False,
                tutor_correct=False, tutor_state="stuck", tutor_action="hint_visual",
                focus_nodes=["flow"], diagnosis="d")
    base.update(kw)
    return RT.Field(**base)


# --- the refusal ------------------------------------------------------------

def test_a_mock_run_is_refused_rather_than_reported():
    """§9.5 reads the MODEL's account of the student. The mock's `diagnosis` is
    a formatted string, and thirty of them measure prompts, not a tutor."""
    assert CONFIG.mock_mode is True, "the suite is hermetic; see conftest"
    assert RT.main.__module__ == RT.__name__


def test_the_refusal_is_wired_to_mock_mode(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["diagnosis_readthrough", "--n", "1"])
    assert RT.main() == 2
    assert "MOCK_MODE" in capsys.readouterr().err


# --- the student answers honestly -------------------------------------------

@pytest.mark.parametrize("expects,pick,attr,value", [
    ("node_click", "tcp_vegas", "node_id", "tcp_vegas"),
    ("mcq", "opt_b", "choice_id", "opt_b"),
])
def test_response_carries_the_pick_as_the_type_the_server_asked_for(
        store, expects, pick, attr, value):
    """Click answers pass through verbatim. Free text does NOT - see
    test_a_free_text_answer_is_prose_not_a_node_id."""
    r = RT._response(store, store.item("itm_0001"), expects, pick)
    assert r.type == expects
    assert getattr(r, attr) == value


def test_an_edge_pick_is_split_back_into_its_endpoints(store):
    """`from->to` is how the student policy names an edge; the wire wants two
    fields. Before adversarial.py grew this split, every edge answer scored 0."""
    r = RT._response(store, store.item("itm_0001"), "edge_click", "a_node->b_node")
    assert r.type == "edge_click"
    assert r.edge.from_ == "a_node" and r.edge.to == "b_node"


# --- scoring ----------------------------------------------------------------

def test_correct_agreement_counts_the_boolean_against_the_actual_click():
    """Call 1 SEES the answer, so anything under 100% is a scoring fault - and
    §7 computes mastery from exactly this boolean."""
    fields = [
        _field(pick_correct=True, tutor_correct=True),
        _field(pick_correct=False, tutor_correct=False),
        _field(pick_correct=True, tutor_correct=False),   # the tutor is wrong
    ]
    ca = RT.score(fields)["correct_agreement"]
    assert ca == {"agree": 2, "of": 3, "rate": round(2 / 3, 4)}


def test_state_is_tabulated_against_the_true_condition_not_against_itself():
    fields = [
        _field(condition="zero", tutor_state="guessing"),
        _field(condition="zero", tutor_state="stuck"),
        _field(condition="partial", tutor_state="confused_prereq"),
    ]
    table = RT.score(fields)["state_by_true_condition"]
    assert table["zero"] == {"guessing": 1, "stuck": 1}
    assert table["partial"] == {"confused_prereq": 1}


def test_a_constant_diagnosis_is_reported_as_degenerate():
    """The failure §9.5 exists to find: a label that never moves."""
    fields = [_field(condition=c, tutor_state="stuck")
              for c in ("zero", "partial", "adversarial")]
    result = RT.score(fields)
    assert result["distinct_states"] == 1
    assert "ONE STATE ACROSS 3 TRUE CONDITIONS" in RT.render(result)


def test_one_condition_is_not_degeneracy(capsys):
    """At small --n the round-robin never leaves `zero`. Warning there would be
    a well-formed complaint about nothing - see numbers-that-looked-fine.md."""
    fields = [_field(condition="zero", tutor_state="stuck") for _ in range(3)]
    out = RT.render(RT.score(fields))
    assert "ONE STATE ACROSS" not in out
    assert "Only 1 of 3 conditions sampled" in out


def test_the_result_carries_its_sampling_provenance():
    prov = RT.score([_field(item_id="itm_0001"), _field(item_id="itm_0006")])["provenance"]
    assert prov["observations"] == 2
    assert prov["unit"] == "diagnoses"
    assert prov["code"], "an eval result must name the build that computed it"


# --- the sheet --------------------------------------------------------------

def test_the_sheet_puts_the_truth_next_to_the_claim():
    """A reader must be able to judge a diagnosis without cross-referencing a
    second file. Both the student's real knowledge and their actual click are
    on the page with it."""
    sheet = RT.render_sheet([_field(condition="partial", student_pick="tcp_vegas",
                                    diagnosis="they conflate the two windows")])
    assert "TRUTH" in sheet
    assert "partial" in sheet
    assert "tcp_vegas" in sheet
    assert "they conflate the two windows" in sheet


def test_the_result_names_the_model_that_wrote_the_diagnoses():
    """§9.5 judges a specific model's account of a student, and these fields
    outlive the run. The build stamp does not imply the model: CALL1_MODEL is
    config, so two builds can differ only in which model spoke."""
    result = RT.score([_field()])
    assert result["call1_model"] == CONFIG.call1.model
    assert result["provider"] == CONFIG.llm_provider
    assert result["call1_model"] in RT.render(result)


def test_a_free_text_answer_is_prose_not_a_node_id(store):
    """`Student.choose` returns an id. Sending it verbatim as free text gives the
    server something no person would type - and the tutor noticed, diagnosing
    "the student keeps offering text instead of clicking". That read as a
    hallucination until the driver was checked."""
    r = RT._response(store, store.item("itm_0001"), "text", "tcp_slow_start")
    assert r.type == "text"
    assert r.text == "I think it's tcp slow start"
    assert "_" not in r.text, "a node id leaked into what the student 'typed'"
