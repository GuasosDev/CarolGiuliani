from django import template

register = template.Library()

@register.filter
def get_attr(obj, attr_name):
    """
    Returns the value of the attribute of the object.
    Usage: {{ obj|get_attr:attr_name }}
    """
    if hasattr(obj, attr_name):
        value = getattr(obj, attr_name)
        if callable(value):
            return value()
        return value
    return ""
