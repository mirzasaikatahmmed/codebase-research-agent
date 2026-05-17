from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """Session authentication without CSRF enforcement.

    DRF's default SessionAuthentication requires a CSRF token on every
    non-safe request, which breaks curl / Postman / Swagger UI flows.
    This subclass skips that check while keeping session-based identity.
    """

    def enforce_csrf(self, request):
        return
