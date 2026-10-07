"""Phase 106: is_known_persona() match/no-match cases."""

from src.hrb_chatbot.common.known_personas import is_known_persona


def test_a_known_combo_matches():
    assert is_known_persona("EMP052", "Eddy Employee", "employee") is True


def test_full_name_match_is_case_and_whitespace_insensitive():
    assert is_known_persona("EMP052", "  eddy EMPLOYEE  ", "employee") is True


def test_unknown_employee_id_does_not_match():
    assert is_known_persona("EMP999", "Eddy Employee", "employee") is False


def test_right_employee_id_wrong_role_does_not_match():
    assert is_known_persona("EMP052", "Eddy Employee", "hr_support") is False


def test_right_employee_id_wrong_name_does_not_match():
    assert is_known_persona("EMP052", "Someone Else", "employee") is False
