import os
import ast
import sys
#import stdlib_list # We will use sys.builtin_module_names and standard libs instead

def get_imported_modules(dir_path):
    imported_modules = set()
    for root, _, files in os.walk(dir_path):
        # Skip virtual env and pyinstaller build folders
        if '.venv' in root or 'build' in root or 'dist' in root or '.git' in root or '__pycache__' in root:
            continue
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        tree = ast.parse(f.read(), filename=file_path)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for name in node.names:
                                imported_modules.add(name.name.split('.')[0])
                        elif isinstance(node, ast.ImportFrom):
                            if node.level == 0 and node.module: # level 0 is absolute import
                                imported_modules.add(node.module.split('.')[0])
                except Exception as e:
                    print(f"Error parsing {file_path}: {e}")
    return imported_modules

# Standard library modules (rough list or check against sys)
stdlib = set(sys.builtin_module_names)
# Common python stdlib modules not in sys.builtin_module_names
common_stdlib = {
    "os", "sys", "time", "datetime", "hashlib", "uuid", "json", "socket", "subprocess", "glob",
    "winreg", "shutil", "ast", "collections", "contextlib", "threading", "platform", "logging",
    "typing", "tempfile", "traceback", "re", "math", "csv", "xml", "urllib", "email", "inspect",
    "functools", "abc", "argparse", "copy", "decimal", "io", "pathlib", "random", "string", "zipfile"
}
stdlib.update(common_stdlib)

# Modules in our own codebase
local_modules = {"backend", "frontend", "license_server", "seed_auth"}

all_imports = get_imported_modules('.')
external_imports = all_imports - stdlib - local_modules

print("Found external imports in codebase:")
for imp in sorted(external_imports):
    print(f" - {imp}")
