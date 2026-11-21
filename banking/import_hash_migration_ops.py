"""
PostgreSQL helpers for banking.0007.
Only alters constraints/indexes on bank_transactions (never other tables).
"""

# No percent signs in this SQL so Django/psycopg mogrify cannot mis-parse it.
POSTGRES_APPLY_SQL = """
DO $migrate$
DECLARE
    constraint_row RECORD;
    index_row RECORD;
    table_name TEXT := 'bank_transactions';
    schema_name TEXT := current_schema();
BEGIN
    FOR constraint_row IN
        SELECT c.conname
        FROM pg_constraint c
        INNER JOIN pg_class t ON c.conrelid = t.oid
        INNER JOIN pg_namespace n ON t.relnamespace = n.oid
        WHERE n.nspname = schema_name
          AND t.relname = table_name
          AND c.contype = 'u'
          AND (
            c.conname IN (
                'bank_transactions_import_hash_key',
                'bank_transactions_import_hash_uniq',
                'bank_transactions_account_import_hash_uniq'
            )
            OR (
                array_length(c.conkey, 1) = 1
                AND EXISTS (
                    SELECT 1
                    FROM pg_attribute a
                    WHERE a.attrelid = t.oid
                      AND a.attnum = c.conkey[1]
                      AND a.attname = 'import_hash'
                      AND NOT a.attisdropped
                )
            )
            OR (
                array_length(c.conkey, 1) = 2
                AND EXISTS (
                    SELECT 1
                    FROM pg_attribute a1
                    WHERE a1.attrelid = t.oid
                      AND a1.attnum = c.conkey[1]
                      AND a1.attname = 'account_name'
                      AND NOT a1.attisdropped
                )
                AND EXISTS (
                    SELECT 1
                    FROM pg_attribute a2
                    WHERE a2.attrelid = t.oid
                      AND a2.attnum = c.conkey[2]
                      AND a2.attname = 'import_hash'
                      AND NOT a2.attisdropped
                )
            )
          )
    LOOP
        EXECUTE
            'ALTER TABLE '
            || quote_ident(schema_name)
            || '.'
            || quote_ident(table_name)
            || ' DROP CONSTRAINT IF EXISTS '
            || quote_ident(constraint_row.conname);
    END LOOP;

    FOR index_row IN
        SELECT ic.relname AS index_name
        FROM pg_index i
        INNER JOIN pg_class t ON i.indrelid = t.oid
        INNER JOIN pg_class ic ON i.indexrelid = ic.oid
        INNER JOIN pg_namespace n ON t.relnamespace = n.oid
        WHERE n.nspname = schema_name
          AND t.relname = table_name
          AND i.indisunique
          AND (
            ic.relname IN (
                'bank_transactions_import_hash_key',
                'bank_transactions_import_hash_uniq',
                'bank_transactions_account_import_hash_uniq'
            )
            OR (
                i.indnatts = 1
                AND EXISTS (
                    SELECT 1
                    FROM pg_attribute a
                    WHERE a.attrelid = t.oid
                      AND a.attnum = i.indkey[0]
                      AND a.attname = 'import_hash'
                      AND NOT a.attisdropped
                )
            )
            OR (
                i.indnatts = 2
                AND EXISTS (
                    SELECT 1
                    FROM pg_attribute a1
                    WHERE a1.attrelid = t.oid
                      AND a1.attnum = i.indkey[0]
                      AND a1.attname = 'account_name'
                      AND NOT a1.attisdropped
                )
                AND EXISTS (
                    SELECT 1
                    FROM pg_attribute a2
                    WHERE a2.attrelid = t.oid
                      AND a2.attnum = i.indkey[1]
                      AND a2.attname = 'import_hash'
                      AND NOT a2.attisdropped
                )
            )
          )
    LOOP
        EXECUTE
            'DROP INDEX IF EXISTS '
            || quote_ident(schema_name)
            || '.'
            || quote_ident(index_row.index_name);
    END LOOP;
END
$migrate$;

CREATE UNIQUE INDEX IF NOT EXISTS bank_transactions_account_import_hash_uniq
ON bank_transactions (account_name, import_hash);
"""

POSTGRES_REVERSE_SQL = """
DO $migrate$
DECLARE
    constraint_row RECORD;
    index_row RECORD;
    table_name TEXT := 'bank_transactions';
    schema_name TEXT := current_schema();
BEGIN
    FOR constraint_row IN
        SELECT c.conname
        FROM pg_constraint c
        INNER JOIN pg_class t ON c.conrelid = t.oid
        INNER JOIN pg_namespace n ON t.relnamespace = n.oid
        WHERE n.nspname = schema_name
          AND t.relname = table_name
          AND c.contype = 'u'
          AND (
            c.conname = 'bank_transactions_account_import_hash_uniq'
            OR (
                array_length(c.conkey, 1) = 2
                AND EXISTS (
                    SELECT 1 FROM pg_attribute a1
                    WHERE a1.attrelid = t.oid AND a1.attnum = c.conkey[1]
                      AND a1.attname = 'account_name' AND NOT a1.attisdropped
                )
                AND EXISTS (
                    SELECT 1 FROM pg_attribute a2
                    WHERE a2.attrelid = t.oid AND a2.attnum = c.conkey[2]
                      AND a2.attname = 'import_hash' AND NOT a2.attisdropped
                )
            )
          )
    LOOP
        EXECUTE
            'ALTER TABLE '
            || quote_ident(schema_name)
            || '.'
            || quote_ident(table_name)
            || ' DROP CONSTRAINT IF EXISTS '
            || quote_ident(constraint_row.conname);
    END LOOP;

    FOR index_row IN
        SELECT ic.relname AS index_name
        FROM pg_index i
        INNER JOIN pg_class t ON i.indrelid = t.oid
        INNER JOIN pg_class ic ON i.indexrelid = ic.oid
        INNER JOIN pg_namespace n ON t.relnamespace = n.oid
        WHERE n.nspname = schema_name
          AND t.relname = table_name
          AND i.indisunique
          AND (
            ic.relname = 'bank_transactions_account_import_hash_uniq'
            OR (
                i.indnatts = 2
                AND EXISTS (
                    SELECT 1 FROM pg_attribute a1
                    WHERE a1.attrelid = t.oid AND a1.attnum = i.indkey[0]
                      AND a1.attname = 'account_name' AND NOT a1.attisdropped
                )
                AND EXISTS (
                    SELECT 1 FROM pg_attribute a2
                    WHERE a2.attrelid = t.oid AND a2.attnum = i.indkey[1]
                      AND a2.attname = 'import_hash' AND NOT a2.attisdropped
                )
            )
          )
    LOOP
        EXECUTE
            'DROP INDEX IF EXISTS '
            || quote_ident(schema_name)
            || '.'
            || quote_ident(index_row.index_name);
    END LOOP;
END
$migrate$;

DO $migrate$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        INNER JOIN pg_class t ON c.conrelid = t.oid
        INNER JOIN pg_namespace n ON t.relnamespace = n.oid
        WHERE n.nspname = current_schema()
          AND t.relname = 'bank_transactions'
          AND c.contype = 'u'
          AND c.conname = 'bank_transactions_import_hash_key'
    ) AND NOT EXISTS (
        SELECT 1
        FROM pg_class ic
        INNER JOIN pg_namespace n ON ic.relnamespace = n.oid
        INNER JOIN pg_index idx ON idx.indexrelid = ic.oid
        INNER JOIN pg_class tab ON idx.indrelid = tab.oid
        WHERE n.nspname = current_schema()
          AND ic.relkind = 'i'
          AND ic.relname = 'bank_transactions_import_hash_key'
          AND tab.relname = 'bank_transactions'
    ) THEN
        CREATE UNIQUE INDEX bank_transactions_import_hash_key
        ON bank_transactions (import_hash);
    END IF;
END
$migrate$;
"""


def postgres_sql_has_no_format_placeholders(sql):
    """Return False if SQL contains chars that break psycopg/Django mogrify."""
    return ("%I" not in sql) and ("%s" not in sql) and ("%%" not in sql)


def execute_postgres_ddl(schema_editor, sql):
    """
    Run DDL without Django's schema_editor.execute() param merging.

    PostgreSQL DatabaseSchemaEditor.execute(sql, ()) calls compose_sql/mogrify,
    which treats literal percent signs in the string as placeholders.
    """
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(sql)


def apply_bank_transaction_unique_index(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    execute_postgres_ddl(schema_editor, POSTGRES_APPLY_SQL)


def reverse_bank_transaction_unique_index(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    execute_postgres_ddl(schema_editor, POSTGRES_REVERSE_SQL)


# Patterns that match schema-wide index drops (unsafe when backup tables exist).
UNSAFE_GLOBAL_INDEX_DROP_PATTERN = "DROP INDEX IF EXISTS bank_transactions_import_hash"


def migration_sql_targets_only_bank_transactions():
    """True when apply SQL scopes work to bank_transactions via pg_catalog."""
    sql = POSTGRES_APPLY_SQL
    if UNSAFE_GLOBAL_INDEX_DROP_PATTERN in sql:
        return False
    if "bank_transactions_bad_backup" in sql:
        return False
    return (
        "t.relname = table_name" in sql
        and "quote_ident(table_name)" in sql
    )