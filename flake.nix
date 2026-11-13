{
  nixConfig = {
    extra-substituters = [
      # https://cache.nixos.org/ has priority 40
      "https://nix-cache.hilorioze.com?priority=41"
    ];

    extra-trusted-public-keys = ["nix-cache.hilorioze.com-1:vKKWGjVDgXl/TXbUWuPWTnDhhDit6hqkTcuoGfter5Y="];
  };

  inputs = {
    flake-parts.url = "github:hercules-ci/flake-parts";

    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

    # keep-sorted start block=yes newline_separated=yes
    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";

      inputs = {
        nixpkgs.follows = "nixpkgs";

        # keep-sorted start
        pyproject-nix.follows = "pyproject-nix";
        uv2nix.follows = "uv2nix";
        # keep-sorted end
      };
    };

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";

      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";

      inputs = {
        nixpkgs.follows = "nixpkgs";

        pyproject-nix.follows = "pyproject-nix";
      };
    };
    # keep-sorted end
  };

  outputs = inputs @ {
    # keep-sorted start
    flake-parts,
    nixpkgs,
    pyproject-build-systems,
    pyproject-nix,
    uv2nix,
    # keep-sorted end
    ...
  }: let
    inherit (nixpkgs) lib;

    systems = ["x86_64-linux"];

    # versions come from `uv.lock`: nixpkgs has no adaptix, dature, dishka, kurigram, secretspec and taskiq
    workspace = uv2nix.lib.workspace.loadWorkspace {workspaceRoot = ./.;};
  in
    flake-parts.lib.mkFlake {inherit inputs;} {
      inherit systems;

      perSystem = {system, ...}: let
        pkgs = import nixpkgs {inherit system;};

        pythonSet = (pkgs.callPackage pyproject-nix.build.packages {python = pkgs.python314;}).overrideScope (lib.composeManyExtensions [
          pyproject-build-systems.overlays.wheel
          (workspace.mkPyprojectOverlay {sourcePreference = "wheel";})
        ]);

        # only the `hilot-*` commands, without the interpreter and the rest of the venv
        application = (pkgs.callPackages pyproject-nix.build.util {}).mkApplication {
          venv = pythonSet.mkVirtualEnv "hilot-env" workspace.deps.default;

          package = pythonSet.hilot;
        };

        package = application.overrideAttrs (previousAttrs: {
          nativeBuildInputs = previousAttrs.nativeBuildInputs ++ [pkgs.makeWrapper];

          # yt-dlp merges formats with ffmpeg and solves youtube's javascript challenges with deno, the workers probe and transcode with ffmpeg
          postFixup = let
            runtimeInputs = with pkgs; [
              # keep-sorted start
              deno
              ffmpeg-headless
              # keep-sorted end
            ];
          in ''
            for program in $out/bin/*; do
              wrapProgram $program --prefix PATH : ${lib.makeBinPath runtimeInputs}
            done
          '';

          meta = {
            description = "Multi-functional Telegram userbot";
            homepage = "https://github.com/hilorioze/hilot";

            license = lib.licenses.mit;

            mainProgram = "hilot-bot";

            platforms = systems;
          };
        });
      in {
        packages = {
          # keep-sorted start
          default = package;
          hilot = package;
          # keep-sorted end
        };
      };

      flake.overlays.default = _final: prev: {inherit (inputs.self.packages.${prev.stdenv.hostPlatform.system}) hilot;};
    };
}
