from django import template

register = template.Library()

@register.filter
def get_attr(obj, attr_name):
    """
    Returns the value of the attribute of the object.
    Supports nested attributes using double underscore (e.g. userprofile__work_area__name)
    Usage: {{ obj|get_attr:attr_name }}
    """
    if not obj:
        return ""
        
    # Handle nested attributes (django style __)
    if "__" in attr_name:
        parts = attr_name.split("__")
        res = obj
        for part in parts:
            if hasattr(res, part):
                res = getattr(res, part)
                if callable(res):
                    res = res()
            else:
                return ""
        return res
        
    if hasattr(obj, attr_name):
        value = getattr(obj, attr_name)
        if callable(value):
            return value()
        return value
    return ""
