from django import template

from grandchallenge.subdomains.utils import reverse

register = template.Library()


# Number of nesting levels rendered in the sidebar. This must match the
# children prefetch in DocPageDetail.get_context_data.
SIDEBAR_MAX_DEPTH = 4


@register.simple_tag
def get_active_page_ids(top_level_pages, current_page):
    """
    Return the ids of the current page and all of its ancestors.
    """

    def find_path(pages, depth):
        if depth >= SIDEBAR_MAX_DEPTH:
            return None

        for page in pages:
            if page.pk == current_page.pk:
                return [page.pk]

            path = find_path(page.children.all(), depth + 1)
            if path is not None:
                return [page.pk, *path]

        return None

    return set(find_path(top_level_pages, 0) or [])


@register.simple_tag
def get_breadcrumbs(page):
    breadcrumbs = []

    current = page.parent
    while current:
        breadcrumbs.insert(
            0,
            {
                "title": current.title,
                "url": reverse(
                    "documentation:detail", kwargs={"slug": current.slug}
                ),
            },
        )
        current = current.parent

    return breadcrumbs
