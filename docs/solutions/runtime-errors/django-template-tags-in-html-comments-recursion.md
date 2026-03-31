---
title: "RecursionError from Django Template Tags Inside HTML Comments"
category: runtime-errors
date: 2026-03-31
issue: 43
tags: [django, templates, debugging, gotcha]
severity: high
symptom: "RecursionError: maximum recursion depth exceeded on any template render"
root_cause: "{% include %} tags inside HTML comments are still processed by Django"
fix: "Replace <!-- --> comments containing template tags with {# #} Django comments"
---

# RecursionError from Django Template Tags Inside HTML Comments

## Problem

When rendering any Django template that included a component (e.g., `_alert.html`, `_loading.html`), the application crashed with:

```
RecursionError: maximum recursion depth exceeded
```

The error occurred on every page render, including the home page.

## Root Cause

Component templates documented their API usage inside HTML comments with actual Django template tags:

```html
<!-- Component: _alert.html
     Usage: {% include "components/_alert.html" with type="success" message="Saved!" %}
-->
```

**Django's template engine processes ALL `{% %}` tags regardless of their position in the HTML document.** HTML comments (`<!-- -->`) are transparent to the template compiler — they exist only for browser rendering. The `{% include %}` tag inside the comment was executed as a real include directive, causing the component to include itself infinitely.

This is a fundamental Django behavior: the template engine operates on the raw template string before any HTML semantics are considered. A `{% include %}` in a comment is identical to a `{% include %}` anywhere else.

## Why It Was Hard to Diagnose

1. **Misleading traceback**: The stack trace showed recursion deep in `django.template.loader_tags` and `django.template.base`, not in user code
2. **Appeared to be inheritance issue**: Since `base.html` included `_alert.html`, and `base_public.html` extended `base.html`, the recursion looked like a template inheritance problem
3. **False lead at low recursion limit**: Setting `sys.setrecursionlimit(50)` produced a traceback pointing to `pygments` imports via `django_extensions`, not the template chain
4. **Comments look inert**: The `{% include %}` was visually inside a comment, so it appeared harmless during code review

## Investigation Steps

1. Suspected template inheritance chain — checked for conflicting template names across apps (none found)
2. Tried rendering `base.html` directly — still recursed, ruling out child template issues
3. Tried rendering individual components via `{% include %}` from inline `Template()` — all failed
4. Set low recursion limit (50) — got misleading pygments import traceback
5. **Binary search** (the breakthrough): Rendered template content starting from different line offsets
6. Line 5 of `_loading.html` (`Usage: {% include "components/_loading.html" ...`) was the trigger
7. Confirmed with minimal reproduction:
   ```python
   Template('<!-- {% include "components/_loading.html" %} -->')
   # RecursionError: maximum recursion depth exceeded
   ```

## Solution

Replace HTML comments with Django template comments (`{# ... #}`). Django comments are stripped during compilation — their contents are never lexed, parsed, or executed.

**Before (broken):**
```html
<!-- Component: _alert.html
     Usage: {% include "components/_alert.html" with type="success" message="Saved!" %}
-->
```

**After (fixed):**
```html
{# Component: _alert.html                                                          #}
{# Context: type="success"|"warning"|"error"|"info", message=str, dismissible=bool #}
```

### Failed Intermediate Fix

An attempt to patch files with `sed 's/ %}$//g'` was too aggressive — it stripped the closing `%}` from ALL template tags (not just those in comments), breaking every component. The files required full rewrites.

**Lesson:** Surgical sed on Django templates is dangerous. When template syntax is broken, rewrite the file rather than attempting regex patches.

## Prevention

### Rule

**Never write `{% %}` or `{{ }}` inside HTML comments in any Django template.** Use `{# #}` for all template-level comments and documentation.

### Pre-commit Hook

Add to `.pre-commit-config.yaml`:

```yaml
- repo: local
  hooks:
    - id: no-django-tags-in-html-comments
      name: "No Django template tags inside HTML comments"
      language: pygrep
      entry: '<!--.*\{[{%]'
      files: '\.html$'
```

### Test: Render All Components Without Recursion

```python
import pytest
from pathlib import Path
from django.template import Template, Context

@pytest.mark.parametrize("template_file", Path("templates/components").glob("_*.html"))
def test_component_renders_without_recursion(template_file):
    source = template_file.read_text()
    t = Template(source)
    # Should not raise RecursionError
    t.render(Context({}))
```

### Test: No Self-Referencing Includes

```python
import re
from pathlib import Path

def test_no_component_includes_itself():
    for path in Path("templates/components").glob("_*.html"):
        content = path.read_text()
        template_path = f"components/{path.name}"
        includes = re.findall(r'{%\s*include\s+["\']([^"\']+)', content)
        assert template_path not in includes, (
            f"{path.name} includes itself — will cause infinite recursion"
        )
```

## Key Takeaway

Django template tags are always live. The only way to suppress them is with Django's own comment syntax (`{# #}` or `{% comment %}...{% endcomment %}`). HTML comments provide zero protection from template compilation. (auto memory [claude])
