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
    path("categories/manage/", views.categories_management, name="categories_management"),
    path("categories/<str:category>/", views.category_detail, name="category_detail"),
    path("rules/", views.rules_management, name="rules_management"),
    path("rules/reapply-preview/", views.rules_reapply_preview, name="rules_reapply_preview"),
    path("rules/<int:rule_id>/edit/", views.edit_rule, name="edit_rule"),
    path("rules/<int:rule_id>/", views.rule_detail, name="rule_detail"),
    path("import/", views.import_bank_csv, name="import_bank_csv"),
    path("import/confirm/", views.confirm_bank_csv_import, name="confirm_bank_csv_import"),
    path("imports/", views.import_log_list, name="import_log_list"),
    path("imports/mirror-cleanup/", views.mirror_cleanup, name="mirror_cleanup"),
    path(
        "imports/<int:import_log_id>/undo/",
        views.undo_import_preview,
        name="undo_import_preview",
    ),
    path(
        "imports/<int:import_log_id>/undo/confirm/",
        views.undo_import_log,
        name="undo_import_log",
    ),
    path("reports/vehicle/", views.vehicle_summary, name="vehicle_summary"),
    path("reports/food/", views.food_summary, name="food_summary"),
    path("reports/subscriptions/", views.subscription_summary, name="subscription_summary"),
    path("reports/categories/", views.category_summary, name="category_summary"),
    path("debt/", views.debt_dashboard, name="debt_dashboard"),
]