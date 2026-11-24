from hilot.presentation.telegram.router import Router

from . import links, watermarks

router: Router = Router()

# only the first handler matching a message handles it, so a command goes before the links
router.include_router(watermarks.router)
router.include_router(links.router)
