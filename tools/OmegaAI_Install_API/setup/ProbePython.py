"""Windows PowerShell-biztos Python 3.12 x64 ellenorzes.

Nem `python -c`-vel fut, hanem fajlkent: kizarja a PowerShell 5.1
argumentum-idezojelezesi hibajat es a korabbi SyntaxError-t.
"""
import struct
import sys


def valid_python(major: int, minor: int, bits: int) -> bool:
    return (major, minor, bits) == (3, 12, 64)


def main() -> int:
    bits = struct.calcsize("P") * 8
    if not valid_python(sys.version_info.major, sys.version_info.minor, bits):
        print(f"HIBAS PYTHON: {sys.version_info.major}.{sys.version_info.minor}, {bits} bit; elvart: Python 3.12 64 bit", file=sys.stderr)
        return 12
    print("OK Python 3.12 x64: " + sys.executable)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
