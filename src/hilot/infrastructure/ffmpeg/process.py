import asyncio
import subprocess
from pathlib import Path


async def run_process(*args: str | Path) -> bytes:
    process: asyncio.subprocess.Process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE
    )

    try:
        stdout: bytes = (await process.communicate())[0]
    finally:
        # a cancelled task would leave the process running
        if process.returncode is None:
            process.kill()
            await process.wait()

    if process.returncode:
        raise subprocess.CalledProcessError(returncode=process.returncode, cmd=args, output=stdout)

    return stdout
