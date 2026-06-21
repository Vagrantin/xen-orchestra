Summary: Xen Orchestra Lite (Community Edition)
Name:    xo-lite
Version: 0.8.0
Release: 1.0.community.1%{?dist}
License: AGPL3-only
URL:     https://github.com/vatesfr/xen-orchestra

BuildArch: noarch

Source0: xo-lite-%{version}.tar.gz

%description
Xen Orchestra Lite (Community Edition), patched to deploy a community-built
XOA image. The XVA URL is resolved at runtime from
https://xo-image.yawn.fi/downloads/image.txt

%prep
%autosetup -p1

%install
install -d -m 755 %{buildroot}/opt/xensource/www
cp -a * %{buildroot}/opt/xensource/www
rm %{buildroot}/opt/xensource/www/LICENSE \
   %{buildroot}/opt/xensource/www/CHANGELOG.md

%files
%license LICENSE
%doc CHANGELOG.md
/opt/xensource/www/assets
/opt/xensource/www/build.json
/opt/xensource/www/favicon.svg
/opt/xensource/www/index.html
/opt/xensource/www/manifest.webmanifest
/opt/xensource/www/xolite.html

%changelog
* Mon Apr 06 2026 Community Build <community@build> - 0.8.0-1.0.community.1
- Community Edition: deploy URL sourced from xo-image.yawn.fi/downloads/image.txt
- Removed lite.xen-orchestra.com fallback loader from index.html
