from grandchallenge.forge import generation_utils

custom_filters = {}


def register_simple_filter(func):
    custom_filters[func.__name__] = func
    return func


@register_simple_filter
def is_json(arg):
    return generation_utils.is_json(arg)


@register_simple_filter
def has_json(arg):
    return any(generation_utils.is_json(item) for item in arg)


@register_simple_filter
def is_image(arg):
    return generation_utils.is_image(arg)


@register_simple_filter
def has_image(arg):
    return any(generation_utils.is_image(item) for item in arg)


@register_simple_filter
def is_file(arg):
    return generation_utils.is_file(arg)


@register_simple_filter
def has_file(arg):
    return any(generation_utils.is_file(item) for item in arg)


@register_simple_filter
def has_example_value(arg):
    return generation_utils.has_example_value(arg)
