from django.urls import path

from . import views


app_name = "research"


urlpatterns = [
    path(
        "",
        views.company_list,
        name="company_list",
    ),
    path(
        "company/<int:company_id>/",
        views.company_dashboard,
        name="company_dashboard",
    ),
]