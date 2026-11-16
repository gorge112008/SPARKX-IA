from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .tools import execute_tool


@login_required
@require_GET
def tool_query(request):
    if any(len(request.GET.getlist(key)) != 1 for key in request.GET):
        return JsonResponse({"error": "Cada argumento debe aparecer una sola vez."}, status=400)
    arguments = request.GET.dict()
    name = arguments.pop("tool", "")
    if "limit" in arguments:
        try:
            arguments["limit"] = int(arguments["limit"])
        except ValueError:
            return JsonResponse({"error": "El límite debe ser un entero."}, status=400)
    try:
        result = execute_tool(actor=request.user, name=name, arguments=arguments)
    except ValidationError as error:
        return JsonResponse({"error": " ".join(error.messages)}, status=400)
    return JsonResponse(result, json_dumps_params={"ensure_ascii": False})
