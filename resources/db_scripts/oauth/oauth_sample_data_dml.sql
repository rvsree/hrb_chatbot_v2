-- Sample data for the OAuth2 simulation tables. Run after oauth_schema_ddl.sql.
-- password_hash/client_secret_hash values below are PLACEHOLDER text, not
-- real bcrypt hashes - replace with real hashes (e.g. via passlib) before
-- this is ever wired into working login code.

INSERT INTO roles (role_name, description) VALUES
    ('employee', 'Can query the HR benefits chatbot'),
    ('manager', 'Same query access as employee today'),
    ('hr_support', 'Can upload/manage documents, plus query')
ON CONFLICT (role_name) DO NOTHING;

INSERT INTO employees (employee_id, full_name, email, password_hash, role_id, department) VALUES
    ('E00001', 'Hana Support', 'hana.support@jpmc.example', 'REPLACE_WITH_REAL_BCRYPT_HASH',
        (SELECT id FROM roles WHERE role_name = 'hr_support'), 'HR'),
    ('E00002', 'Eddy Employee', 'eddy.employee@jpmc.example', 'REPLACE_WITH_REAL_BCRYPT_HASH',
        (SELECT id FROM roles WHERE role_name = 'employee'), 'Engineering'),
    ('E00003', 'Mona Manager', 'mona.manager@jpmc.example', 'REPLACE_WITH_REAL_BCRYPT_HASH',
        (SELECT id FROM roles WHERE role_name = 'manager'), 'Sales')
ON CONFLICT (employee_id) DO NOTHING;

INSERT INTO oauth_clients (client_id, client_secret_hash, client_name) VALUES
    ('postman-client', 'REPLACE_WITH_REAL_BCRYPT_HASH', 'Postman (manual testing)')
ON CONFLICT (client_id) DO NOTHING;
