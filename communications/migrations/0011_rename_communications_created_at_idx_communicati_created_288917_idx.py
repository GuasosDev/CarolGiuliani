from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('communications', '0010_internalchatmessage'),
    ]

    def _rename_index(schema_editor, table_name, old_name, new_name):
        connection = schema_editor.connection
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, table_name)
        existing = set(constraints.keys())
        if new_name in existing or old_name not in existing:
            return

        qn = schema_editor.quote_name
        vendor = connection.vendor

        if vendor == 'mysql':
            schema_editor.execute(
                f'ALTER TABLE {qn(table_name)} RENAME INDEX {qn(old_name)} TO {qn(new_name)}'
            )
            return

        schema_editor.execute(
            f'ALTER INDEX {qn(old_name)} RENAME TO {qn(new_name)}'
        )

    def _rename_index_back(schema_editor, table_name, old_name, new_name):
        connection = schema_editor.connection
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, table_name)
        existing = set(constraints.keys())
        if old_name in existing or new_name not in existing:
            return

        qn = schema_editor.quote_name
        vendor = connection.vendor

        if vendor == 'mysql':
            schema_editor.execute(
                f'ALTER TABLE {qn(table_name)} RENAME INDEX {qn(new_name)} TO {qn(old_name)}'
            )
            return

        schema_editor.execute(
            f'ALTER INDEX {qn(new_name)} RENAME TO {qn(old_name)}'
        )

    def forwards(apps, schema_editor):
        Migration._rename_index(
            schema_editor=schema_editor,
            table_name='communications_internalchatmessage',
            old_name='communications_created_at_idx',
            new_name='communicati_created_288917_idx',
        )

    def backwards(apps, schema_editor):
        Migration._rename_index_back(
            schema_editor=schema_editor,
            table_name='communications_internalchatmessage',
            old_name='communications_created_at_idx',
            new_name='communicati_created_288917_idx',
        )

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
