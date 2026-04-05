Summary: Xen Orchestra Lite (Community Edition)
Name:    xo-lite
Version: 0.8.0
# Release suffix convention per xcp-ng: keep lower than any official update
# so that an upstream RPM update always takes precedence.
Release: 1.0.community.1%{?dist}
License: AGPL3-only
URL:     https://github.com/vatesfr/xen-orchestra

BuildArch: noarch

# Source0 is supplied as a local file during the CI build —
# the tarball is built from source in the workflow, not downloaded.
Source0: xo-lite-%{version}.tar.gz

%description
This package contains Xen Orchestra Lite (Community Edition), patched to
deploy a community-built XOA image instead of the official Vates appliance.
The XVA URL is resolved at runtime from https://xo-image.yawn.fi/downloads/image.txt

%prep
%autosetup -p1

%install
install -d -m 755 %{buildroot}/opt/xensource/www
cp -a * %{buildroot}/opt/xensource/www
rm %{buildroot}/opt/xensource/www/LICENSE %{buildroot}/opt/xensource/www/CHANGELOG.md

%files
%license LICENSE
/opt/xensource/www/assets
/opt/xensource/www/index.html
/opt/xensource/www/favicon.svg
/opt/xensource/www/manifest.webmanifest
/opt/xensource/www/xolite.html
%doc CHANGELOG.md

%changelog
* Sun Apr 06 2026 Community Build <community@build> - 0.8.0-1.0.community.1
- Community Edition: deploy URL sourced from xo-image.yawn.fi/downloads/image.txt
- Removed lite.xen-orchestra.com fallback loader from index.html
