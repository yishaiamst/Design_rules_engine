# Debug Scripts Guide

## Timeout and Timing Requirements

**All debug scripts must:**
1. ✅ Use `timeout` context manager for overall script timeout
2. ✅ Use `Timer` context manager for timing operations
3. ✅ Be optimized to avoid long-running operations

## Usage

### Import Timeout Utilities

```python
from utils.timeout_utils import timeout, Timer, TimeoutError
```

### Wrap Main Function with Timeout

```python
def main():
    try:
        with timeout(600):  # 10 minutes
            # Your code here
            pass
    except TimeoutError as e:
        print(f"Timeout: {e}")
        sys.exit(1)
```

### Time Individual Operations

```python
with Timer("Loading data"):
    data = load_data()

with Timer("Processing items"):
    results = process_items(data)
```

### Example: Optimized Debug Script

```python
#!/usr/bin/env python3
import sys
from utils.timeout_utils import timeout, Timer, TimeoutError

def main():
    try:
        with timeout(300):  # 5 minutes
            with Timer("Loading data"):
                data = load_data()
            
            with Timer("Processing"):
                results = process(data)
            
            with Timer("Saving results"):
                save_results(results)
    
    except TimeoutError:
        print("Script timed out after 5 minutes")
        sys.exit(1)
    except KeyboardInterrupt:
        print("Interrupted by user")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

## Optimization Tips

1. **Use spatial indexing** for geometry matching
2. **Limit iterations** (e.g., check first 100 items)
3. **Use set operations** instead of nested loops
4. **Cache results** when possible
5. **Process in batches** for large datasets

## Timeout Limits

- **Quick debug scripts**: 2-5 minutes
- **Full pipeline tests**: 10 minutes
- **Comparison scripts**: 10 minutes
- **Analysis scripts**: 5 minutes

