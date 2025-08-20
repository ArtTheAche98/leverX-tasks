from rest_framework.response import Response

class PaginationMixin:
    """Shared helper to reduce pagination boilerplate."""

    def paginate_and_respond(self, queryset, serializer_cls, many=True):
        page = self.paginate_queryset(queryset)
        serializer = serializer_cls(page or queryset, many=many)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)