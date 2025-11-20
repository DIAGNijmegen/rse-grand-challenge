from django import template

from grandchallenge.forge import generation_utils

register = template.Library()


@register.filter
def is_json(arg):
    return generation_utils.is_json(arg)


@register.filter
def has_json(arg):
    return any(generation_utils.is_json(item) for item in arg)


@register.filter
def is_image(arg):
    return generation_utils.is_image(arg)


@register.filter
def has_image(arg):
    return any(generation_utils.is_image(item) for item in arg)


@register.filter
def is_file(arg):
    return generation_utils.is_file(arg)


@register.filter
def is_string(arg):
    return isinstance(arg, str)


@register.filter
def has_file(arg):
    return any(generation_utils.is_file(item) for item in arg)


@register.filter
def has_example_value(arg):
    return generation_utils.has_example_value(arg)


@register.filter(name="zip")
def zip_items(a, b):
    return zip(a, b, strict=True)


@register.filter
def dash_to_underscore(arg):
    return arg.replace("-", "_")
