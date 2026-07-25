# ── shared ────────────────────────────────────────────
PROJECT := "azathoth"
VERSION := `git describe --tags --always`

[default]
[group('meta')]
list:
    @just --list --unsorted
