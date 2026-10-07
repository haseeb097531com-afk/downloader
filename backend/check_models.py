import re, os

# Models
models = []
for f in os.listdir('app/models'):
    if f.endswith('.py') and f not in ('__init__.py', 'base.py'):
        text = open(f'app/models/{f}').read()
        m = re.search(r'__tablename__\s*=\s*["\']([^"\']+)["\']', text)
        if m:
            models.append(m.group(1))
print('Models:', sorted(models))

# Migrations - match both formats:
# op.create_table('name', ...)
# op.create_table(
#     "name", ...
migrations = []
for f in sorted(os.listdir('alembic/versions')):
    if f.endswith('.py'):
        text = open(f'alembic/versions/{f}').read()
        # Format 1: op.create_table('name', ...) or op.create_table("name", ...)
        found = re.findall(r'op\.create_table\(\s*["\']([^"\']+)["\']\s*,', text)
        # Format 2: op.create_table(\n    "name", ...
        found += re.findall(r'op\.create_table\(\s*\n\s*["\']([^"\']+)["\']\s*,', text)
        migrations.extend(found)
print('Created tables:', sorted(set(migrations)))

model_set = set(models)
mig_set = set(migrations)
print('Missing migrations:', sorted(model_set - mig_set))
print('Extra migrations:', sorted(mig_set - model_set))
