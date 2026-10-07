"""Phase 106: a small fixed roster for lightweight login validation - not a
real user directory, just enough to deny an unknown/typo'd identity instead
of accepting anything typed into the login form. Extends the EMP051/EMP052
identities already used throughout postman/ and tests/, not new ones."""

KNOWN_PERSONAS = {
    "EMP051": {"full_name": "Hana Support", "role": "hr_support"},
    "EMP052": {"full_name": "Eddy Employee", "role": "employee"},
    "EMP053": {"full_name": "Mia Manager", "role": "manager"},
}


def is_known_persona(employee_id: str, full_name: str, role: str) -> bool:
    persona = KNOWN_PERSONAS.get(employee_id)
    if persona is None:
        return False
    if persona["full_name"].strip().lower() != full_name.strip().lower():
        return False
    return persona["role"] == role
