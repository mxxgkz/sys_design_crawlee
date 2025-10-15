# RAG App Development Guide

## 🚨 **CRITICAL: Path Management**

**ALWAYS** use the common setup to avoid path issues:

### ✅ **Correct Way (Use This)**
```python
#!/usr/bin/env python3
"""
Your script description.
"""

# ALWAYS start with this import
from rag_app.common_setup import setup_environment, get_database_path, get_storage_path, get_vector_db_path

# Now import other modules
import sqlite3
from pathlib import Path

def main():
    # Use the path functions
    db_path = get_database_path()
    storage_path = get_storage_path()
    # Your code here...

if __name__ == "__main__":
    main()
```

### ❌ **Wrong Way (Don't Do This)**
```python
# DON'T do this - causes path issues
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.chdir(project_root)
```

## 📁 **Available Path Functions**

- `get_database_path()` - Returns path to `storage/table_data.db`
- `get_storage_path()` - Returns path to `storage/` directory
- `get_vector_db_path()` - Returns path to `storage/vector_db/`
- `get_project_root()` - Returns project root directory

## 🔧 **Common Setup Features**

The `common_setup.py` automatically:
1. ✅ Sets correct working directory
2. ✅ Adds project root to Python path
3. ✅ Provides standardized path functions
4. ✅ Works from any subdirectory

## 📋 **Script Template**

Use `rag_app/script_template.py` as a starting point for new scripts.

## 🚨 **Path Issue Symptoms**

If you see these errors, you have a path issue:
- `FileNotFoundError: [Errno 2] No such file or directory: 'storage/table_data.db'`
- Database shows 0 bytes when it should have data
- Scripts can't find files that exist

## 🔧 **Quick Fix for Existing Scripts**

Add this to the top of any problematic script:
```python
from rag_app.common_setup import setup_environment
setup_environment()
```

## 📝 **Best Practices**

1. **Always** import `common_setup` first
2. **Use** the provided path functions
3. **Don't** hardcode paths like `"storage/table_data.db"`
4. **Test** scripts from different directories
5. **Use** the script template for new files

## 🎯 **Remember**

- ✅ Use `common_setup` - No path issues
- ❌ Manual path setup - Path issues guaranteed
