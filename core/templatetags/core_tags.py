from django import template

register = template.Library()

def _display_value(value):
    """Vacío / None → guión tipográfico para listados."""
    if value is None:
        return "—"
    if isinstance(value, str) and value.strip() in ("", "None", "none"):
        return "—"
    return value


@register.filter
def get_attr(obj, attr_name):
    """
    Returns the value of the attribute of the object.
    Supports nested attributes using double underscore (e.g. userprofile__work_area__name)
    Usage: {{ obj|get_attr:attr_name }}
    """
    if not obj:
        return "—"

    # Handle nested attributes (django style __)
    if "__" in attr_name:
        parts = attr_name.split("__")
        res = obj
        for part in parts:
            if hasattr(res, part):
                res = getattr(res, part)
                if callable(res):
                    res = res()
                if res is None:
                    return "—"
            else:
                return "—"
        return _display_value(res)

    if hasattr(obj, attr_name):
        value = getattr(obj, attr_name)
        if callable(value):
            value = value()
        return _display_value(value)
    return "—"
