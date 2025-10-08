{
  description = "Development environment for MCP for Rust and Python (via uv)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }: let
    system = "x86_64-linux";
    pkgs = nixpkgs.legacyPackages.${system};
  in {
    devShells.${system}.default = pkgs.mkShell {
      packages = [
        pkgs.cargo
        pkgs.uv
      ];
      shellHook = ''
        echo "Welcome to the MCP development environment!"
        echo "You can run 'cargo build' to build the Rust project."
        echo "You can run 'uv' to use the uv tool."
      '';
    };
  };
}

