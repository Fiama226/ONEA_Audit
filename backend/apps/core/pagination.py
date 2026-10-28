from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Default pagination: 25 items, client-adjustable up to 200."""

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200
