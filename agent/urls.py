from django.urls import path
from agent.views import LoginView, LogoutView, RepositoryListView, SessionDetailView, SessionListCreateView

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("sessions/", SessionListCreateView.as_view(), name="session-list-create"),
    path("sessions/<int:pk>/", SessionDetailView.as_view(), name="session-detail"),
    path("repos/", RepositoryListView.as_view(), name="repo-list"),
]
