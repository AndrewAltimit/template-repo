Here's the patch:

```diff
diff --git a/src/app.py b/src/app.py
index 1234567..89abcde 100644
--- a/src/app.py
+++ b/src/app.py
@@ -1,4 +1,4 @@
 import os
 
-def greet(name):
-    return "Hello " + name
+def greet(name: str) -> str:
+    return f"Hello {name}"
@@ -10,2 +10,3 @@ def main():
 def main():
     greet("world")
+    return 0
--- /dev/null
+++ b/CHANGELOG.md
@@ -0,0 +1,2 @@
+# Changelog
+- typed greet
```

Let me know if you want tests too.
