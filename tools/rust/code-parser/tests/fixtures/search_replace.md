Two edits are needed.

src/app.py
```python
<<<<<<< SEARCH
def greet(name):
    return "Hello " + name
=======
def greet(name: str) -> str:
    return f"Hello {name}"
>>>>>>> REPLACE
```

```python
<<<<<<< SEARCH
VERSION = "1.0"
=======
VERSION = "1.1"
>>>>>>> REPLACE
```

Also create a new file:

tests/test_app.py
```python
<<<<<<< SEARCH
=======
from app import greet

def test_greet():
    assert greet("x") == "Hello x"
>>>>>>> REPLACE
```

Finally, in file `setup.cfg`, change `version = 1.0` to `version = 1.1`.
