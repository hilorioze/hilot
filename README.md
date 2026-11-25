# hilot

A multi-functional Telegram userbot.

## Features

### Downloads

A link in an outgoing or a private message gets the media behind it as a reply.

The media of a link and of `.dl` goes out with the title, the description and the author of its post, as much as the site gives, cut to the caption limit of Telegram; an album has the caption once per post.

`.dl` or `.download` downloads the links given to it. In reply to a message, it downloads the links of that message and sends the media in reply to it.

Under the command, `.dl` writes the result of each post, its title leading to the message with the media by a `t.me/c/` link, which opens only in supergroups and channels, and the error of each failed link.

The commands work in any chat, saved messages included; in a private chat, the other side's commands get the answer in reply. They also work in a reply to a message from another chat: Telegram gives such a reply only the quoted text, the link preview and the media of that message, so `.dl` takes the quoted and previewed links and `.synth` checks the media.

### SynthID check

`.synth` or `.synthid` in reply to a photo, a video or an audio, or as its caption, checks it for a [SynthID](https://synthid.com/) watermark and writes the verdict under the command.

The checks take every synthid.com account signed in from the browser of `hilot-detector`; each has a daily quota per media kind, so the next one takes over. Signing out doesn't remove an account, so they are signed in one after another in the same window.

## Running

- `hilot-bot`: the Telegram client
- `hilot-downloader`: downloads the media into S3
- `hilot-transcoder`: converts the media Telegram can't play to H.264, AAC and JPEG
- `hilot-detector`: checks the media for a SynthID watermark on synthid.com, with the accounts signed in from its browser
- `hilot-login`: logs in with a QR code, or with a phone number on the test backend, and prints the session string
- `hilot-cookies <cookies.txt>`: stores the cookies of a logged in browser for the sites that need a login, replacing the stored cookies of the sites in the file; with `--whole-browser` the file holds the whole browser, so the sites missing from it lose their stored cookies too
- `hilot-migrate`: [Alembic](https://alembic.sqlalchemy.org/) for the database, e.g. `hilot-migrate upgrade head`

The commands share PostgreSQL, [NATS](https://nats.io/) with JetStream and an S3 bucket; there is one `hilot-bot` per Telegram account. The workers serve `/healthz` and Prometheus `/metrics` on their `http` address.

- with [devenv](https://devenv.sh/): `devenv up` starts PostgreSQL, NATS and [Garage](https://garagehq.deuxfleurs.fr/) and migrates the database; then `hilot-login` and the workers in `devenv shell`
- with Nix: `nix shell github:hilorioze/hilot`

## Configuration

`hilot.toml` is read from the working directory, `~/.config`, `/etc` or `/etc/xdg`. [The one in the repository](hilot.toml) is for devenv.

- `[telegram]`: the app and the device hilot logs in as; `hilot-login` and `hilot-bot` need the same one
- `telegram.test_mode`: `hilot-login` logs in to [the test backend](https://core.telegram.org/api/auth#test-accounts); the session string keeps it for `hilot-bot`
- `bot.max_message_age`: messages older than this that came in while `hilot-bot` was down are skipped
- `bot.check_ins`: once a day, at a random moment between `start` and `end`, sends `command` to `bot` and presses `buttons` by their callback data; only on the accounts that have started the bot
- `s3.reuse_period`: how long the other accounts send a stored file from the bucket instead of downloading it again
- `disk.min_free_space`: a download or a transcode that would leave less free waits for `disk.postpone_delay`
- `detector.browser_url`: the DevTools address of a Chromium-based browser started apart from `hilot-detector`, with `--remote-debugging-port`; synthid.com attests the requests in a real page, which refuses a browser automated from its start, and the synthid.com accounts are signed in from its windows
- `concurrency`: the number of tasks a worker runs at once

Secrets come from [secretspec](https://secretspec.dev/); the `development` profile has the ones of the devenv services.

| Secret | Commands | |
| --- | --- | --- |
| `SESSION_STRING` | bot | the output of `hilot-login` |
| `ENCRYPTION__KEYS` | downloader, detector, cookies | JSON list of [Fernet](https://cryptography.io/en/latest/fernet/) keys for the cookies and the synthid.com accounts in the database; the first one encrypts, so a new key goes first |
| `DOWNLOADER__PROXY` | downloader | optional proxy URL for the downloads |
| `NATS__TOKEN` | bot, downloader, transcoder, detector | |
| `S3__ACCESS_KEY_ID`, `S3__SECRET_ACCESS_KEY` | bot, downloader, transcoder, detector | |

## Development

`devenv test` runs treefmt (ruff, alejandra, deadnix, statix, keep-sorted, tombi), pyright, actionlint, eclint, flake-checker and a merge conflict check.

- `src/hilot/domain/`: entities, value objects, errors and the interfaces of the adapters and repositories
- `src/hilot/application/`: use cases
- `src/hilot/infrastructure/`: adapters on kurigram, yt-dlp, gallery-dl, ffmpeg, SQLAlchemy, S3, taskiq and synthid.com
- `src/hilot/presentation/`: Telegram handlers and reply texts, taskiq tasks and HTTP endpoints
- `src/hilot/main/`: config, dishka providers and the commands

## License

[MIT](LICENSE)
