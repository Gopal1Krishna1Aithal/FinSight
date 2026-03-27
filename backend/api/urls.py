from django.urls import path
from . import views

urlpatterns = [
    path("upload/",               views.upload_statement,   name="upload_statement"),
    path("insights/",             views.get_insights,       name="get_insights"),
    path("download/tally-csv/",   views.download_tally_csv, name="download_tally_csv"),
    path("download/tally-xml/",   views.download_tally_xml, name="download_tally_xml"),
    path("download/excel/",       views.download_excel,     name="download_excel"),
    path("dashboard/",            views.get_dashboard,      name="get_dashboard"),
    path("chat/",                 views.chat_query,         name="chat_query"),
    path("status/",               views.get_status,         name="get_status"),
]
