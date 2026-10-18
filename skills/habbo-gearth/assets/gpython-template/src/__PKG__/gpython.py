"""Single import point for g_python.

g-python 0.1.6 has ``x is not 'NULL'`` comparisons that make Python 3.12+ print
SyntaxWarnings when the module is first compiled. They're harmless, so this module
silences them and re-exports what the extension needs. Import g_python classes from
here, never from ``g_python`` directly.
"""

import warnings

with warnings.catch_warnings():
    warnings.simplefilter("ignore", SyntaxWarning)
    from g_python.gextension import Extension
    from g_python.hdirection import Direction
    from g_python.hmessage import HMessage
    from g_python.hpacket import HPacket

__all__ = ["Direction", "Extension", "HMessage", "HPacket"]
