{
  description = "a ritual to channel the unseen";

  inputs = {
    utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:NixOS/nixpkgs/master";
    nix-filter.url = "github:numtide/nix-filter";
  };

  outputs = {
    self,
    nixpkgs,
    utils,
    nix-filter,
  }: utils.lib.eachDefaultSystem(system: let
    pkgs = import nixpkgs {
      inherit system;
    };

    filter = nix-filter.lib;

    buildPythonPackage = pkgs.python3Packages.buildPythonPackage;
    buildPythonApplication = pkgs.python3Packages.buildPythonApplication;

    PythonSed = (buildPythonPackage rec {
      pname = "PythonSed";
      version = "1.00";

      src = pkgs.fetchFromGitHub {
        owner = "modwizcode";
        repo = "PythonSed";
        rev = "f9e736dee73cbdd6db534b3834aaf39c867de568";
        hash = "sha256-UFZCC3QDHBAlypPPSSHrNhy2kv4gMlTJ5wtnQp6vJYM=";
      };
    });
  in {
    packages = {
      default = buildPythonApplication {
        name = "seance";

        src = filter {
          root = ./.;
        };

        format = "pyproject";

        buildInputs = with pkgs.python3Packages; [
          setuptools
        ];

        propagatedBuildInputs = with pkgs.python3Packages; [
          python-telegram-bot
          discordpy
          PythonSed
          emoji
          sdnotify
        ];
      };
    };

  }) // {
    nixosModule = {config, lib, pkgs, ...}:
      with lib;
      let
        cfg = config.services.seance;
      in {
        options.services.seance = {
          enable = mkEnableOption "Enables the Seance module";

          systems = mkOption {
            description = "Systems to configure Seance for";
            default = {};
            type = types.attrsOf (types.submodule {
              options = {
                referenceUserID = mkOption {
                  description = "User ID to follow";
                  type = types.str;
                };

                peerPattern = mkOption {
                  description = "Regular expression that matches the message pattern of all bots in this system";
                  type = types.nullOr types.str;
                };

                autoproxyLatchScope = mkOption {
                  description = "What scope this system's autoproxy should latch at";
                  type = types.enum [ "global" "server" "channel" ];
                  default = "server";
                };

                autoproxyLatchTimeout = mkOption {
                  description = "How long autoproxy latch mode should stay latched (in seconds)";
                  type = types.nullOr types.ints.positive;
                };

                autoproxyLatchStartEnabled = mkEnableOption "Whether this system's bots should start in latching autoproxy mode";

                defaultPresence = mkOption {
                  description = "The presence option to set upon startup";
                  type = types.nullOr (types.enum [ "invisible" "dnd" "idle" "online" "sync" "latch" ]);
                };

                forwardPings = mkEnableOption "Whether this system's bots should forward pings back to the followed user";

                members = mkOption {
                  description = "The members of this system";
                  default = {};
                  type = types.attrsOf (types.submodule {
                    options = {
                      discordToken = mkOption {
                        description = "Discord app token for this member's seance bot";
                        type = types.str;
                      };

                      messagePattern = mkOption {
                        description = "Regular expression that matches messages that this bot should proxy";
                        type = types.str;
                      };

                      commandPrefix = mkOption {
                        description = "String prefix that allows commands to be sent to just this bot";
                        type = types.nullOr types.str;
                      };
                    };
                  });
                };
              };
            });
          };
        };

        config = mkIf cfg.enable {
          systemd.services = lib.listToAttrs (lib.flatten (lib.mapAttrsToList (systemName: system: lib.mapAttrsToList (memberName: member: (
            nameValuePair "seance-${systemName}-${memberName}" {
              description = "Seance discord bot for ${memberName} (${systemName})";

              wantedBy = [ "multi-user.target" ];

              after = [ "network.target" ];
              wants = [ "network.target" ];

              environment = { PYTHONUNBUFFERED = "1"; };

              serviceConfig = let pkg = self.packages.${pkgs.system}.default; in {
                Type = "notify";
                Restart = "always";
                DynamicUser = true;

                PrivateTmp = true;
                ProtectSystem = "full";
                NoNewPrivileges = true;
                PrivateDevices = true;
                MemoryDenyWriteExecute = true;

                ExecStart = ''
                  ${pkg}/bin/seance-discord \
                    --systemd-notify \
                    --token ${member.discordToken} \
                    --ref-user-id ${system.referenceUserID} \
                    --pattern ${lib.escapeShellArg member.messagePattern} \
                    ${optionalString (system.peerPattern != null) "--peer-pattern ${lib.escapeShellArg system.peerPattern}"} \
                    ${optionalString (member.commandPrefix != null) "--prefix ${member.commandPrefix}"} \
                    --autoproxy-latch-scope ${system.autoproxyLatchScope} \
                    ${optionalString (system.autoproxyLatchTimeout != null) "--autoproxy-latch-timeout ${toString system.autoproxyLatchTimeout}"} \
                    ${optionalString system.autoproxyLatchStartEnabled "--autoproxy-start-enabled"} \
                    ${optionalString (system.defaultPresence != null) "--default-presence ${system.defaultPresence}"} \
                    ${optionalString system.forwardPings "--forward-pings"}
                '';
              };
            })) system.members) cfg.systems));
        };
      };
  };

}
