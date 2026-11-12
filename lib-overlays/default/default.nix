final: prev: {
  lazy-purifier = {
    readLock = import ./read-lock.nix { lib = final; };
  };
}
