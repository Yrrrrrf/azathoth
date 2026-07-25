{
  description = "Development environment for Azathoth (Python 3.14 via uv)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }: let
    system = "x86_64-linux";
    pkgs = nixpkgs.legacyPackages.${system};
  in {
    devShells.${system}.default = pkgs.mkShell {
      packages = [
        pkgs.python314
        pkgs.uv
      ];
      shellHook = ''
        echo "Welcome to the Azathoth development environment!"
        echo "You can run 'uv' to manage the Python 3.14 toolchain."
      '';
    };
  };
}
