import app.main
app = app.main.app
for i, r in enumerate(app.routes):
    if type(r).__name__ == '_IncludedRouter':
        print(f'{i}: original_router prefix = {getattr(r.original_router, "prefix", None)}')
        for j, sub in enumerate(r.original_router.routes):
            if hasattr(sub, 'path'):
                print(f'   route {j}: {sub.path} {getattr(sub, "methods", set())}')
