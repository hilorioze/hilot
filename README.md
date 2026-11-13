# hilot

A multi-functional Telegram userbot.

## Running

- `hilot-bot`: the Telegram client
- `hilot-downloader`: downloads the media into S3
- `hilot-transcoder`: converts the media Telegram can't play to H.264, AAC and JPEG
- `hilot-login`: logs in with a QR code, or with a phone number on the test backend, and prints the session string
- `hilot-cookies <cookies.txt>`: stores the cookies of a logged in browser for the sites that need a login
- `hilot-migrate`: [Alembic](https://alembic.sqlalchemy.org/) for the database, e.g. `hilot-migrate upgrade head`

The commands share PostgreSQL, [NATS](https://nats.io/) with JetStream and an S3 bucket; there is one `hilot-bot` per Telegram account. `hilot-bot`, `hilot-downloader` and `hilot-transcoder` serve `/healthz` and Prometheus `/metrics` on their `http` address.

- with [devenv](https://devenv.sh/): `devenv up` starts PostgreSQL, NATS and [Garage](https://garagehq.deuxfleurs.fr/) and migrates the database; then `hilot-login` and the three workers in `devenv shell`
- with Nix: `nix shell github:hilorioze/hilot`

## Configuration

`hilot.toml` is read from the working directory, `~/.config`, `/etc` or `/etc/xdg`. [The one in the repository](hilot.toml) is for devenv.

- `[telegram]`: the app and the device hilot logs in as; `hilot-login` and `hilot-bot` need the same one
- `telegram.test_mode`: `hilot-login` logs in to [the test backend](https://core.telegram.org/api/auth#test-accounts); the session string keeps it for `hilot-bot`
- `bot.max_message_age`: messages older than this that came in while `hilot-bot` was down are skipped
- `bot.check_ins`: once a day, at a random moment between `start` and `end`, sends `command` to `bot` and presses `buttons` by their callback data; only on the accounts that have started the bot
- `s3.reuse_period`: how long the other accounts send a delivered file from the bucket instead of downloading it again
- `disk.min_free_space`: a download or a transcode that would leave less free waits for `disk.postpone_delay`
- `concurrency`: the number of tasks a worker runs at once

Secrets come from [secretspec](https://secretspec.dev/); the `development` profile has the ones of the devenv services.

| Secret | Commands | |
| --- | --- | --- |
| `SESSION_STRING` | bot | the output of `hilot-login` |
| `COOKIES__KEYS` | downloader, cookies | JSON list of [Fernet](https://cryptography.io/en/latest/fernet/) keys; the first one encrypts, so a new key goes first |
| `DOWNLOADER__PROXY` | downloader | optional proxy URL for the downloads |
| `NATS__TOKEN` | bot, downloader, transcoder | |
| `S3__ACCESS_KEY_ID`, `S3__SECRET_ACCESS_KEY` | bot, downloader, transcoder | |

## Development

`devenv test` runs treefmt (ruff, alejandra, deadnix, statix, keep-sorted, tombi), pyright, actionlint, eclint, flake-checker and a merge conflict check.

- `src/hilot/domain/`: entities, value objects, errors and the interfaces of the adapters and repositories
- `src/hilot/application/`: use cases
- `src/hilot/infrastructure/`: adapters on kurigram, yt-dlp, gallery-dl, ffmpeg, SQLAlchemy, S3 and taskiq
- `src/hilot/presentation/`: Telegram handlers and reply texts, taskiq tasks and HTTP endpoints
- `src/hilot/main/`: config, dishka providers and the commands

## License

[MIT](LICENSE)
