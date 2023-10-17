import re
import hashlib
from typing import Dict
from typer.main import TyperGroup


def md5(string):
    md = hashlib.md5()
    md.update(string.encode("utf-8"))
    return md.hexdigest()


def highlight(str1, substr1, color):
    if not substr1 or len(substr1) == 0:
        return str1
    p = re.compile(re.escape(substr1), re.IGNORECASE)
    for m in p.findall(str1):
        str1 = p.sub(f"[{color}]{m}[/{color}]", str1)
    return str1


def get_typer_commands(group: TyperGroup) -> Dict[str, Dict]:
    _map = {}
    for name, command in group.commands.items():
        if not isinstance(command, TyperGroup):
            _map[name] = None
        else:
            _map[name] = get_typer_commands(command)
    return _map
