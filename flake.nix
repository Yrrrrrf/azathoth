{
  description = "Development environment for assembly programming and Python tools";

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
        (pkgs.writeShellScriptBin "run-asm" (builtins.readFile ./src/run-asm.sh))
      ];
      shellHook = ''
        echo "Welcome to the assembly and Python development environment!"
        echo "You can use 'run-asm <source_file>' to assemble and run assembly code."
      '';
    };
  };
}

