import re
import hashlib
import inspect


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


def generate_default_value(return_type):
    if return_type is inspect.Signature.empty:
        return None
    elif return_type is bool:
        return False
    elif return_type is int:
        return 0
    elif return_type is float:
        return 0.0
    elif return_type is str:
        return ""
    elif return_type is list:
        return []
    elif return_type is dict:
        return {}
    elif return_type is tuple:
        return ()
    else:
        return None
