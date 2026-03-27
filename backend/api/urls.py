from django.urls import path
from . import views

urlpatterns = [
    path("upload/",             views.upload_statement, name="upload_statement"),
    path("insights/",           views.get_insights,    name="get_insights"),
    path("download/tally-csv/", views.download_tally_csv, name="download_tally_csv"),
    path("download/tally-xml/", views.download_tally_xml, name="download_tally_xml"),
    path("status/",             views.get_status,      name="get_status"),
]
