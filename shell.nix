let
  pkgs = import <nixpkgs> {};
in pkgs.mkShell {
  packages = [
    (pkgs.python3.withPackages (python-pkgs: [
      python-pkgs.certifi
      python-pkgs.charset-normalizer
      python-pkgs.idna
      python-pkgs.protobuf
      python-pkgs.requests
      python-pkgs.simplekml
      python-pkgs.urllib3
    ]))
  ];
}
