"""Makes server output safe to paste into an AI tool or commit (security/ai-policy.md).

    some-command | python3 ops/redact.py --keep 159.89.228.242

Replaced:
- visitors' IP addresses, IPv4 (with or without a :port) and IPv6. Private and loopback addresses (Docker's own
  network) are kept, as are any given with --keep, such as the server's address, which is in the site's name anyway.
- anything shaped like a Discord webhook URL
- the value after password=, secret: or token= and the like

Dotted numbers right after a word and a slash, such as Chrome/130.0.0.0 or nginx/1.30.6, are versions, not addresses.
Standard library only, since it runs on the server with the system's Python.
"""

import argparse
import ipaddress
import re
import sys

WEBHOOK = re.compile(r"https://(?:canary\.|ptb\.)?discord(?:app)?\.com/api/webhooks/[^\s\"']+")
SECRET_VALUE = re.compile(r"((?:password|secret|token)[=:]\s*)[^\s,\"']+", re.IGNORECASE)
IPV4 = re.compile(r"(?<![\w.:])(?<![A-Za-z]/)\d{1,3}(?:\.\d{1,3}){3}(?![\w.])")
IPV6 = re.compile(r"(?<![\w.:])[0-9a-fA-F]{0,4}(?::[0-9a-fA-F]{0,4}){2,7}(?![\w.:])")


def redact(line: str, keep: frozenset[str] = frozenset()) -> str:
    def address(match: re.Match) -> str:
        text = match.group(0)
        try:
            ip = ipaddress.ip_address(text)
        except ValueError:
            return text  # looked like an address but isn't one, such as a time (08:01:02)
        if text in keep or ip.is_private or ip.is_loopback or ip.is_unspecified:
            return text
        return "<ip>"

    line = WEBHOOK.sub("<discord-webhook-url>", line)
    line = SECRET_VALUE.sub(r"\1<redacted>", line)
    return IPV6.sub(address, IPV4.sub(address, line))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--keep", action="append", default=[], help="an address to leave as it is")
    keep = frozenset(parser.parse_args().keep)
    for line in sys.stdin:
        sys.stdout.write(redact(line, keep))
        sys.stdout.flush()  # line by line, so a long-running script's output appears as it happens


if __name__ == "__main__":
    main()
