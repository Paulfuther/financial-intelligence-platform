"""
PostgreSQL helpers for banking.0007.
Only alters constraints/indexes on bank_transactions (never other tables).
"""

# Applied on PostgreSQL only. Uses pg_catalog to target bank_transactions.
POSTGRES_APPLY_SQL = """
DO $migrate$
DECLARE
    constraint_row RECORD;
    index_row RECORD;
BEGIN
    FOR constraint_row IN
        SELECT c.conname
        FROM pg_constraint c
        INNER JOIN pg_class t ON c.conrelid = t.oid
        INNER JOIN pg_namespace n ON t.relnamespace = n.oid
        WHERE n.nspname = current_schema()
          AND t.relname = 'bank_transactions'
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
        EXECUTE format(
            'ALTER TABLE %I.%I DROP CONSTRAINT IF EXISTS %I',
            current_schema(),
            'bank_transactions',
            constraint_row.conname
        );
    END LOOP;

    FOR index_row IN
        SELECT ic.relname AS index_name
        FROM pg_index i
        INNER JOIN pg_class t ON i.indrelid = t.oid
        INNER JOIN pg_class ic ON i.indexrelid = ic.oid
        INNER JOIN pg_namespace n ON t.relnamespace = n.oid
        WHERE n.nspname = current_schema()
          AND t.relname = 'bank_transactions'
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
        EXECUTE format(
            'DROP INDEX IF EXISTS %I.%I',
            current_schema(),
            index_row.index_name
        );
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
BEGIN
    FOR constraint_row IN
        SELECT c.conname
        FROM pg_constraint c
        INNER JOIN pg_class t ON c.conrelid = t.oid
        INNER JOIN pg_namespace n ON t.relnamespace = n.oid
        WHERE n.nspname = current_schema()
          AND t.relname = 'bank_transactions'
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
        EXECUTE format(
            'ALTER TABLE %I.%I DROP CONSTRAINT IF EXISTS %I',
            current_schema(),
            'bank_transactions',
            constraint_row.conname
        );
    END LOOP;

    FOR index_row IN
        SELECT ic.relname AS index_name
        FROM pg_index i
        INNER JOIN pg_class t ON i.indrelid = t.oid
        INNER JOIN pg_class ic ON i.indexrelid = ic.oid
        INNER JOIN pg_namespace n ON t.relnamespace = n.oid
        WHERE n.nspname = current_schema()
          AND t.relname = 'bank_transactions'
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
        EXECUTE format(
            'DROP INDEX IF EXISTS %I.%I',
            current_schema(),
            index_row.index_name
        );
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
        WHERE n.nspname = current_schema()
          AND ic.relkind = 'i'
          AND ic.relname = 'bank_transactions_import_hash_key'
          AND EXISTS (
              SELECT 1
              FROM pg_index idx
              INNER JOIN pg_class tab ON idx.indrelid = tab.oid
              WHERE idx.indexrelid = ic.oid
                AND tab.relname = 'bank_transactions'
          )
    ) THEN
        CREATE UNIQUE INDEX bank_transactions_import_hash_key
        ON bank_transactions (import_hash);
    END IF;
END
$migrate$;
"""


def apply_bank_transaction_unique_index(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(POSTGRES_APPLY_SQL)


def reverse_bank_transaction_unique_index(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(POSTGRES_REVERSE_SQL)


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
        "t.relname = 'bank_transactions'" in sql
        and "ALTER TABLE %I.%I DROP CONSTRAINT" in sql
    )