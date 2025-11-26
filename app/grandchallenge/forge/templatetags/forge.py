from django import template

register = template.Library()


@register.filter
def has_json(arg):
    return any(item.is_json for item in arg)


@register.filter
def has_image(arg):
    return any(item.is_image for item in arg)


@register.filter
def is_string(arg):
    return isinstance(arg, str)


@register.filter
def has_file(arg):
    return any(item.is_file for item in arg)


@register.filter(name="zip")
def zip_items(a, b):
    return zip(a, b, strict=True)


@register.filter
def dash_to_underscore(arg):
    return arg.replace("-", "_")
