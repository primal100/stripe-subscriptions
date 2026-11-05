#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo 'Usage: publish.sh [--build-only] [--repository pypi|testpypi] [--python PATH]'
    echo 'Requires Python 3.11+ with build and twine installed.'
}

repository=pypi
python_bin=python3
build_only=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --build-only) build_only=true; shift ;;
        --repository|--python)
            if [[ $# -lt 2 || -z "$2" ]]; then
                usage >&2
                exit 2
            fi
            if [[ "$1" == --repository ]]; then repository=$2; else python_bin=$2; fi
            shift 2
            ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
done
if [[ "$repository" != pypi && "$repository" != testpypi ]]; then
    usage >&2
    exit 2
fi

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
# Install these in the selected interpreter first: python3 -m pip install build twine
"$python_bin" -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ is required"; import build, twine'

mkdir -p dist
release_directory=$(mktemp -d "$PWD/dist/release-XXXXXXXX")
"$python_bin" -m build --outdir "$release_directory"

shopt -s nullglob
wheels=("$release_directory"/*.whl)
archives=("$release_directory"/*.tar.gz)
if [[ ${#wheels[@]} -ne 1 || ${#archives[@]} -ne 1 ]]; then
    echo 'Expected exactly one wheel and one source distribution; publishing stopped.' >&2
    exit 1
fi
artifacts=("${wheels[0]}" "${archives[0]}")
"$python_bin" -m twine check --strict "${artifacts[@]}"

echo "Validated distributions: $release_directory"
if [[ "$build_only" == true ]]; then
    echo 'Build-only mode: nothing uploaded.'
else
    echo "Uploading to $repository. Enter that repository's API token if prompted."
    "$python_bin" -m twine upload --repository "$repository" --username __token__ "${artifacts[@]}"
fi
