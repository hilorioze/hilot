from http.cookiejar import Cookie as JarCookie
from http.cookiejar import CookieJar

from hilot.domain.value_objects.cookie import Cookie


def fill_cookie_jar(*, jar: CookieJar, cookies: list[Cookie]) -> None:
    for cookie in cookies:
        jar.set_cookie(
            JarCookie(
                version=0,
                name=cookie.name,
                value=cookie.value,
                port=None,
                port_specified=False,
                domain=cookie.domain,
                # how cookies.txt marks a cookie of the subdomains too
                domain_specified=cookie.include_subdomains,
                domain_initial_dot=cookie.domain.startswith("."),
                path=cookie.path,
                path_specified=True,
                secure=cookie.secure,
                expires=cookie.expires,
                discard=cookie.expires is None,
                comment=None,
                comment_url=None,
                rest={},
            )
        )


def read_cookie_jar(jar: CookieJar) -> list[Cookie]:
    # without the expired cookies, so they get deleted from the database too
    jar.clear_expired_cookies()

    return [
        Cookie(
            domain=cookie.domain,
            path=cookie.path,
            name=cookie.name,
            value=cookie.value,
            expires=cookie.expires,
            include_subdomains=cookie.domain_specified,
            secure=cookie.secure,
        )
        for cookie in jar
        # a cookie set without a value has nothing to keep
        if cookie.value is not None
    ]
