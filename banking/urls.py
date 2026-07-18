from django.urls import path
from . import views

app_name = "banking"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path(

        "dashboard/category-preview/",

        views.category_transaction_preview,

        name="category_transaction_preview",

    ),
    path(

    "transactions/<int:transaction_id>/update-category/",

    views.update_transaction_category,

    name="update_transaction_category",

),
    path("rules/", views.rules_management, name="rules_management"),
    path("rules/<int:rule_id>/edit/", views.edit_rule, name="edit_rule"),
    path(
    "rules/<int:rule_id>/edit/",
    views.edit_rule,
    name="edit_rule"
),
    path("rules/<int:rule_id>/", views.rule_detail, name="rule_detail"),
    path(
    "categories/<str:category>/",
    views.category_detail,
    name="category_detail",
),
    path("import/", views.import_bank_csv, name="import_bank_csv"),
    path("imports/", views.import_log_list, name="import_log_list"),
    path(
    "categories/<str:category>/",
    views.category_detail,
    name="category_detail",
),
    path("reports/vehicle/", views.vehicle_summary, name="vehicle_summary"),
    path("reports/food/", views.food_summary, name="food_summary"),
    path("reports/subscriptions/", views.subscription_summary, name="subscription_summary"),
    # path("import/", views.import_bank_csv_preview, name="import_bank_csv"),
    path("import/confirm/", views.confirm_bank_csv_import, name="confirm_bank_csv_import"),
    path("debt/", views.debt_dashboard, name="debt_dashboard"),
    path("reports/categories/", views.category_summary, name="category_summary"),
]