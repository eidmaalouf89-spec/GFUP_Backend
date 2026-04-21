"""
src/pipeline/utils.py
---------------------
Shared console-output utility used by stages and compute helpers.
"""

import sys


def _safe_console_print(*args, **kwargs):
    """
    Print safely on Windows consoles using legacy encodings.
    """
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")
        text = sep.join(str(arg) for arg in args)
        sanitized = (
            text.replace("—", "-")
            .replace("–", "-")
            .replace("â€”", "-")
            .replace("→", "->")
            .replace("â†’", "->")
            .replace("✅", "[OK]")
            .replace("âœ…", "[OK]")
            .replace("❌", "[ERROR]")
            .replace("âŒ", "[ERROR]")
            .replace("⚠️", "[WARN]")
            .replace("⚠", "[WARN]")
        )
        sys.stdout.write(sanitized + end)

