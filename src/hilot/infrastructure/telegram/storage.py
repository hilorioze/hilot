from collections.abc import Iterable
from datetime import timedelta
from typing import Any, override

from pyrogram.raw.base.input_peer import InputPeer
from pyrogram.storage.sqlite_storage import PROD, TEST, SQLiteStorage, get_input_peer
from pyrogram.storage.storage import MISSING, Storage, UpdateState
from sqlalchemy import ScalarResult, Select, delete, func, select
from sqlalchemy.dialects.postgresql import Insert, insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from hilot.infrastructure.database.sql.models.peer import PeerModel
from hilot.infrastructure.database.sql.models.update_state import UpdateStateModel
from hilot.infrastructure.database.sql.models.username import UsernameModel
from hilot.infrastructure.database.sql.upsert import upsert

from .authorization import Authorization


# keep the authorization from the session string in memory and the peers and update states in the database
class SQLStorage(Storage):
    def __init__(
        self, *, authorization: Authorization, session_maker: async_sessionmaker[AsyncSession]
    ) -> None:
        self._account_id: int = authorization.user_id
        self._session_maker: async_sessionmaker[AsyncSession] = session_maker

        self._mtproto_session: dict[str, Any] = {
            "dc_id": authorization.dc_id,
            "api_id": authorization.api_id,
            # the addresses and ports kurigram connects a new session to
            "server_address": (TEST if authorization.test_mode else PROD)[authorization.dc_id],
            "port": 80 if authorization.test_mode else 443,
            "test_mode": authorization.test_mode,
            "auth_key": authorization.auth_key,
            "date": 0,
            "user_id": authorization.user_id,
            "is_bot": authorization.is_bot,
        }

    @override
    async def open(self) -> None:
        # the container opens and closes the database engine
        pass

    @override
    async def close(self) -> None:
        pass

    @override
    async def save(self) -> None:
        # every write commits right away
        pass

    @override
    async def delete(self) -> None:
        async with self._session_maker() as session, session.begin():
            await session.execute(
                delete(UsernameModel).where(UsernameModel.account_id == self._account_id)
            )
            await session.execute(
                delete(PeerModel).where(PeerModel.account_id == self._account_id)
            )
            await session.execute(
                delete(UpdateStateModel).where(UpdateStateModel.account_id == self._account_id)
            )

    @override
    async def update_peers(self, peers: Iterable[tuple[int, int, str, str | None]]) -> None:
        async with self._session_maker() as session, session.begin():
            await upsert(
                session=session,
                model=PeerModel,
                rows=[
                    {
                        "account_id": self._account_id,
                        "peer_id": peer_id,
                        "access_hash": access_hash,
                        "peer_type": peer_type,
                        "phone_number": phone_number,
                    }
                    for peer_id, access_hash, peer_type, phone_number in peers
                ],
            )

    @override
    async def update_usernames(self, usernames: Iterable[tuple[int, list[str | None]]]) -> None:
        async with self._session_maker() as session, session.begin():
            await session.execute(
                delete(UsernameModel).where(
                    UsernameModel.account_id == self._account_id,
                    UsernameModel.peer_id.in_([peer_id for peer_id, _ in usernames]),
                )
            )

            await session.execute(
                insert(UsernameModel)
                .values(
                    [
                        {"account_id": self._account_id, "peer_id": peer_id, "username": username}
                        for peer_id, names in usernames
                        for username in names
                    ]
                )
                # kurigram handles updates concurrently, so another update may insert the same username first
                .on_conflict_do_nothing()
            )

    @override
    async def get_update_states(self, ids: int | Iterable[int] | None = None) -> list[UpdateState]:
        statement: Select[UpdateStateModel] = select(UpdateStateModel).where(
            UpdateStateModel.account_id == self._account_id
        )

        if ids is not None:
            statement = statement.where(UpdateStateModel.state_id.in_(self._list_ids(ids)))

        async with self._session_maker() as session:
            models: ScalarResult[UpdateStateModel] = await session.scalars(
                statement.order_by(UpdateStateModel.date)
            )

            return [
                UpdateState(model.state_id, model.pts, model.qts, model.date, model.seq)
                for model in models
            ]

    @override
    async def set_update_state(self, update_state: UpdateState | Iterable[UpdateState]) -> None:
        states: Iterable[UpdateState] = (
            [update_state] if isinstance(update_state, UpdateState) else update_state
        )
        statement: Insert = insert(UpdateStateModel).values(
            [
                {
                    "account_id": self._account_id,
                    "state_id": state.id,
                    "pts": state.pts,
                    "qts": state.qts,
                    "date": state.date,
                    "seq": state.seq,
                }
                for state in states
            ]
        )

        async with self._session_maker() as session, session.begin():
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[UpdateStateModel.account_id, UpdateStateModel.state_id],
                    set_={
                        # kurigram passes `None` for the fields an update leaves as they are
                        column.name: func.coalesce(
                            column, UpdateStateModel.__table__.c[column.name]
                        )
                        for column in statement.excluded
                        if not column.primary_key
                    },
                )
            )

    @override
    async def delete_update_state(self, state_id: int | Iterable[int]) -> None:
        async with self._session_maker() as session, session.begin():
            await session.execute(
                delete(UpdateStateModel).where(
                    UpdateStateModel.account_id == self._account_id,
                    UpdateStateModel.state_id.in_(self._list_ids(state_id)),
                )
            )

    @override
    async def get_peer_by_id(self, peer_id: int) -> InputPeer:
        return await self._get_peer(
            statement=select(PeerModel).where(
                PeerModel.account_id == self._account_id, PeerModel.peer_id == peer_id
            ),
            key=peer_id,
        )

    @override
    async def get_peer_by_username(self, username: str) -> InputPeer:
        return await self._get_peer(
            statement=select(PeerModel)
            .join(UsernameModel)
            .where(
                UsernameModel.account_id == self._account_id,
                UsernameModel.username == username,
                # a username can move to another peer, so let kurigram resolve it again after its ttl
                PeerModel.updated_at > func.now() - timedelta(seconds=SQLiteStorage.USERNAME_TTL),
            )
            .order_by(PeerModel.updated_at.desc()),
            key=username,
        )

    @override
    async def get_peer_by_phone_number(self, phone_number: str) -> InputPeer:
        return await self._get_peer(
            statement=select(PeerModel).where(
                PeerModel.account_id == self._account_id, PeerModel.phone_number == phone_number
            ),
            key=phone_number,
        )

    @override
    async def dc_id(self, value: int | type[object] | None = MISSING) -> int | None:
        return self._access_mtproto_session(name="dc_id", value=value)

    @override
    async def api_id(self, value: int | type[object] | None = MISSING) -> int | None:
        return self._access_mtproto_session(name="api_id", value=value)

    @override
    async def server_address(self, value: str | type[object] | None = MISSING) -> str | None:
        return self._access_mtproto_session(name="server_address", value=value)

    @override
    async def port(self, value: int | type[object] | None = MISSING) -> int | None:
        return self._access_mtproto_session(name="port", value=value)

    @override
    async def test_mode(self, value: bool | type[object] | None = MISSING) -> bool | None:
        return self._access_mtproto_session(name="test_mode", value=value)

    @override
    async def auth_key(self, value: bytes | type[object] | None = MISSING) -> bytes | None:
        return self._access_mtproto_session(name="auth_key", value=value)

    @override
    async def date(self, value: int | type[object] | None = MISSING) -> int | None:
        return self._access_mtproto_session(name="date", value=value)

    @override
    async def user_id(self, value: int | type[object] | None = MISSING) -> int | None:
        return self._access_mtproto_session(name="user_id", value=value)

    @override
    async def is_bot(self, value: bool | type[object] | None = MISSING) -> bool | None:
        return self._access_mtproto_session(name="is_bot", value=value)

    async def _get_peer(self, *, statement: Select[PeerModel], key: int | str) -> InputPeer:
        async with self._session_maker() as session:
            model: PeerModel | None = await session.scalar(statement)

        if model is None:
            # kurigram looks a peer up in the storage first and asks telegram on a `KeyError`
            raise KeyError(key)

        return get_input_peer(
            peer_id=model.peer_id, access_hash=model.access_hash, peer_type=model.peer_type
        )

    def _access_mtproto_session[T](self, *, name: str, value: T | type[object] | None) -> T | None:
        # `None` is a value too, kurigram sets the user id to it on a logout
        if value is not MISSING:
            self._mtproto_session[name] = value

        return self._mtproto_session[name]

    @staticmethod
    def _list_ids(ids: int | Iterable[int]) -> list[int]:
        return [ids] if isinstance(ids, int) else list(ids)
