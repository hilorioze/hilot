# hilot

A multi-functional Telegram userbot.

## Features

- **Downloads**: media from the links in outgoing and private messages, and from `.dl` / `.download`, with the title, author and description of the post
- **SynthID check**: `.synth` / `.synthid` checks a photo, video or audio, or the media of a link, for a [SynthID](https://synthid.com/) watermark
- **Transcription**: voice messages in private chats, and `.stt` on any voice, audio or video, transcribed with Whisper on [Groq](https://groq.com/)

The commands work in any chat, on the message they reply to or the one they're sent with.

## Running

- `hilot-bot`: the Telegram client
- `hilot-downloader`: downloads the media into S3
- `hilot-transcoder`: converts the media Telegram can't play to H.264, AAC and JPEG
- `hilot-detector`: checks the media for a SynthID watermark on synthid.com, with the accounts signed in from its browser
- `hilot-transcriber`: transcribes the speech of the media with Whisper on Groq
- `hilot-login`: logs in with a QR code, or with a phone number on the test backend, and prints the session string
- `hilot-cookies <cookies.txt>`: stores the cookies of a logged in browser for the sites that need a login, replacing the stored cookies of the sites in the file; with `--whole-browser` the file holds the whole browser, so the sites missing from it lose their stored cookies too
- `hilot-cleanup`: deletes the cached data that has expired, to run daily
- `hilot-migrate`: [Alembic](https://alembic.sqlalchemy.org/) for the database, e.g. `hilot-migrate upgrade head`

The commands share PostgreSQL, [NATS](https://nats.io/) with JetStream and an S3 bucket; there is one `hilot-bot` per Telegram account. The workers serve `/healthz` and Prometheus `/metrics` on their `http` address.

- with [devenv](https://devenv.sh/): `devenv up` starts PostgreSQL, NATS and [Garage](https://garagehq.deuxfleurs.fr/) and migrates the database; then `hilot-login` and the workers in `devenv shell`
- with Nix: `nix shell github:hilorioze/hilot`

## Configuration

`hilot.toml` is read from the working directory, `~/.config`, `/etc` or `/etc/xdg`. [The one in the repository](hilot.toml) is for devenv.

- `[telegram]`: the app and the device hilot logs in as; `hilot-login` and `hilot-bot` need the same one
- `telegram.test_mode`: `hilot-login` logs in to [the test backend](https://core.telegram.org/api/auth#test-accounts); the session string keeps it for `hilot-bot`
- `[inline_bot]`: the bot whose inline results bring rich messages, for the captions that don't fit, albums of over 10 media and long transcripts; an account sends them once it has started the bot, and a chat that refuses inline bots gets plain messages
- `inline_bot.local_mode`: `api_url` is a [Bot API server](https://github.com/tdlib/telegram-bot-api) started with `--local`, which takes files of up to 2000 MB
- `bot.max_message_age`: messages older than this that came in while `hilot-bot` was down are skipped
- `bot.check_ins`: once a day, at a random moment between `start` and `end`, sends `command` to `bot` and presses `buttons` by their callback data; only on the accounts that have started the bot
- `stored_file.reuse_period`: how long the other accounts send a stored file from the bucket instead of downloading it again
- `disk.min_free_space`: a download or a transcode that would leave less free waits for `disk.postpone_delay`
- `detector.browser_url`: the DevTools address of a Chromium-based browser started apart from `hilot-detector`, with `--remote-debugging-port`; synthid.com attests the requests in a real page, which refuses a browser automated from its start, and the synthid.com accounts are signed in from its windows; signing out keeps an account, so they go one after another in the same window
- `concurrency`: the number of tasks a worker runs at once

Secrets come from [secretspec](https://secretspec.dev/); the `development` profile has the ones of the devenv services.

| Secret | Commands | |
| --- | --- | --- |
| `SESSION_STRING` | bot | the output of `hilot-login` |
| `INLINE_BOT__TOKEN` | bot | |
| `ENCRYPTION__KEYS` | downloader, detector, cookies | JSON list of [Fernet](https://cryptography.io/en/latest/fernet/) keys for the cookies and the synthid.com accounts in the database; the first one encrypts, so a new key goes first |
| `DOWNLOADER__PROXY` | downloader | optional proxy URL for the downloads |
| `GROQ__API_KEY` | transcriber | |
| `NATS__TOKEN` | bot, downloader, transcoder, detector, transcriber | |
| `S3__ACCESS_KEY_ID`, `S3__SECRET_ACCESS_KEY` | bot, downloader, transcoder, detector, transcriber | |

## Development

`devenv test` runs treefmt (ruff, alejandra, deadnix, statix, keep-sorted, tombi), pyright, actionlint, eclint, flake-checker and a merge conflict check.

- `src/hilot/domain/`: entities, value objects, errors and the interfaces of the adapters and repositories
- `src/hilot/application/`: use cases
- `src/hilot/infrastructure/`: adapters on kurigram, aiogram, yt-dlp, gallery-dl, ffmpeg, Groq, SQLAlchemy, S3, taskiq and synthid.com
- `src/hilot/presentation/`: Telegram handlers and reply texts, taskiq tasks and HTTP endpoints
- `src/hilot/main/`: config, dishka providers and the commands

## License

[MIT](LICENSE)
