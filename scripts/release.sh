#!/bin/bash
# Release script

set -e

VERSION=$1

if [ -z "$VERSION" ]; then
    echo "Usage: $0 <version>"
    exit 1
fi

echo "Releasing version $VERSION..."
git tag "v$VERSION"
git push origin "v$VERSION"
echo "Done!"
