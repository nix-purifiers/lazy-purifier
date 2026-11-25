# Installed SDK templates contain literal paths. Restore the realized union's
# store context so Nix retains and mounts its actual module dependency closure.
config:
if config == { } then
  { }
else
  config
  // {
    environment = builtins.storePath config.environment;
  }
