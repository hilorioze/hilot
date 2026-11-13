from aiohttp import web
from prometheus_client.aiohttp import make_aiohttp_handler


async def get_health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


def create_http_app() -> web.Application:
    app: web.Application = web.Application()

    app.router.add_get("/healthz", get_health)
    app.router.add_get("/metrics", make_aiohttp_handler())

    return app
