from dishka import Provider, Scope, from_context, provide

from hilot.domain.interfaces.adapters.disk_space import DiskSpace
from hilot.domain.interfaces.adapters.media_prober import MediaProber
from hilot.domain.interfaces.adapters.media_transcoder import MediaTranscoder
from hilot.domain.interfaces.adapters.workspace import Workspace
from hilot.infrastructure.ffmpeg.prober import FfprobeMediaProber
from hilot.infrastructure.ffmpeg.transcoder import FfmpegMediaTranscoder
from hilot.infrastructure.filesystem.disk_space import LocalDiskSpace
from hilot.infrastructure.filesystem.workspace import TemporaryWorkspace
from hilot.main.config.disk import DiskConfig
from hilot.presentation.taskiq.media import PostponeDelay


class WorkspaceProvider(Provider):
    workspace = provide(TemporaryWorkspace, provides=Workspace, scope=Scope.APP)


class DiskSpaceProvider(Provider):
    config = from_context(provides=DiskConfig, scope=Scope.APP)

    # one counter of the reserved space for every task of the process
    @provide(scope=Scope.APP)
    def get_disk_space(self, config: DiskConfig) -> DiskSpace:
        return LocalDiskSpace(min_free_space=int(config.min_free_space))

    @provide(scope=Scope.APP)
    def get_postpone_delay(self, config: DiskConfig) -> PostponeDelay:
        return PostponeDelay(config.postpone_delay)


class FfmpegProvider(Provider):
    media_prober = provide(FfprobeMediaProber, provides=MediaProber, scope=Scope.APP)
    media_transcoder = provide(FfmpegMediaTranscoder, provides=MediaTranscoder, scope=Scope.APP)
