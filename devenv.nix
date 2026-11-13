{
  config,
  lib,
  pkgs,
  ...
}: {
  env = {
    # the secretspec cli looks for `secretspec.toml` only in the working directory and its parents, hilot reads it from its package
    SECRETSPEC_FILE = "${config.devenv.root}/src/hilot/secretspec.toml";

    SECRETSPEC_PROFILE = "development";
  };

  languages = {
    # keep-sorted start block=yes newline_separated=yes
    nix = {
      enable = true;

      lsp.package = pkgs.nil;
    };

    python = {
      enable = true;

      uv = {
        enable = true;

        sync.enable = true;
      };

      # `uv.sync` creates the venv but doesn't add it to `PATH`
      venv.enable = true;
    };
    # keep-sorted end
  };

  treefmt = {
    enable = true;

    config.programs = {
      # keep-sorted start block=yes newline_separated=yes
      alejandra = {
        enable = true;

        priority = 100;
      };

      deadnix.enable = true;

      keep-sorted.enable = true;

      ruff-check.enable = true;

      ruff-format.enable = true;

      statix.enable = true;
      # keep-sorted end
    };

    # treefmt-nix has no module for tombi
    config.settings.formatter.tombi = {
      command = lib.getExe pkgs.tombi;
      options = ["format"];

      includes = ["*.toml"];
    };
  };

  git-hooks.hooks = let
    ignoredShellcheckRules = [
      # keep-sorted start
      "SC2016" # expressions in single quotes; intentional, the quoted text is not meant to expand
      "SC2086" # unquoted variables; referenced are safe
      "SC2162" # `read` without `-r`; intentional too, paths and stuff don't have backslashes
      # keep-sorted end
    ];
  in {
    # keep-sorted start block=yes newline_separated=yes
    actionlint = {
      enable = true;

      args = map (code: "-ignore=${code}") ignoredShellcheckRules;
    };

    check-merge-conflicts = {
      enable = true;

      fail_fast = true; # abort immediately so treefmt never runs on conflicted files
    };

    # use `.editorconfig` as the single source of truth for generic file normalization
    eclint = {
      enable = true;

      types = ["text"];

      # `eclint` only processes the first positional path, so let it discover tracked files itself
      pass_filenames = false;

      settings.fix = true;
    };

    flake-checker.enable = true;

    pyright.enable = true;

    treefmt = {
      enable = true;

      after = ["check-merge-conflicts"];
    };
    # keep-sorted end
  };

  packages = with pkgs; [
    # keep-sorted start
    deno # yt-dlp needs it to solve youtube's js challenges
    ffmpeg
    secretspec
    # keep-sorted end
  ];

  services = {
    # keep-sorted start block=yes newline_separated=yes
    garage = {
      enable = true;

      buckets = ["hilot"];

      # the development profile of `secretspec.toml` defaults to this key
      afterStart = ''
        garage key info hilot >/dev/null 2>&1 || garage key import --yes -n hilot GK46f7300711cd187ca6509d8c 407c73910872f207cd80faa0eab38e171baecaaa7c3bbda9f958994b572e0e8f
        garage bucket allow --read --write --owner hilot --key hilot
      '';
    };

    nats = {
      enable = true;

      jetstream.enable = true;

      # the development profile of `secretspec.toml` defaults to this token
      authorization = {
        enable = true;

        token = "hilot";
      };
    };

    postgres = {
      enable = true;

      initialDatabases = [{name = "hilot";}];
    };
    # keep-sorted end
  };

  devcontainer = {
    enable = true;

    settings = {
      onCreateCommand = ''sudo sh -c 'printf "accept-flake-config = true\n" >> /etc/nix/nix.conf' '';

      # cache `/nix` between rebuilds
      mounts = ["source=devcontainer-nix,target=/nix,type=volume"];

      customizations.vscode.extensions = [
        # keep-sorted start
        "EditorConfig.EditorConfig"
        "charliermarsh.ruff"
        "jnoortheen.nix-ide"
        "mkhl.direnv"
        "ms-python.python"
        "tombi-toml.tombi"
        # keep-sorted end
      ];
    };
  };

  tasks = {
    "hilot:migrate" = {
      exec = "hilot-migrate upgrade head";

      after = [
        # keep-sorted start
        "devenv:processes:postgres"
        "devenv:python:uv"
        # keep-sorted end
      ];
      # `wantedBy` runs it under `devenv up` too, which otherwise skips the tasks after a process
      wantedBy = ["devenv:processes:postgres"];
    };

    # ensure generated files (like `.devcontainer/devcontainer.json`) exist before `treefmt` runs to prevent race conditions
    "devenv:treefmt:run".after = ["devenv:files"];

    # give pyright the venv: `devenv:python:uv` exports it only to the tasks that run after it
    "devenv:git-hooks:run".after = ["devenv:python:uv"];
  };
}
