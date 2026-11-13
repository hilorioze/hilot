from hilot.presentation.telegram.router import Router

from . import links

router: Router = Router()

router.include_router(links.router)
