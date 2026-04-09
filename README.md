# XCP-ng Community Edition — ISO Builder

> **Unofficial community build of XCP-ng 8.3 with a patched XO Lite.**
> Not supported by Vates. Everything in the official XCP-ng release is
> preserved; only the XO Lite "Deploy XOA" behaviour is changed.

---

## Repository layout

```
.
├── patches/
│   └── community-xoa-deploy.patch   # Git patch applied to vatesfr/xen-orchestra
├── SPECS/
│   └── xo-lite-community.spec       # RPM spec for the community XO Lite package
└── .github/workflows/
    └── community-xoa-deploy.yml     # GitHub Actions workflow (ISO builder)
```

### Branch strategy

| Branch | Purpose |
|---|---|
| `master` | Mirror of `vatesfr/xen-orchestra` — kept in sync with upstream, **never diverges** |
| `patchxolite` | Working branch — ISO build workflow and all community patches live here |

The ISO build workflow is triggered only on pushes to `patchxolite` (or via
`workflow_dispatch`). The `master` branch exists solely to make upstream
rebasing straightforward.

---

## What this build changes

The official XCP-ng ISO ships a web application called **XO Lite** — a
lightweight Xen Orchestra UI served directly from the host at
`/opt/xensource/www/`. XO Lite includes a "Deploy XOA" page that downloads
and provisions a full Xen Orchestra virtual appliance (XVA).

This build makes two targeted changes to XO Lite and leaves everything else
in the ISO untouched.

### Change 1 — Remove the `lite.xen-orchestra.com` phone-home loader

**File:** `@xen-orchestra/lite/scripts/xolite-loader.html`

The official `xolite-loader.html` (served as `index.html` on the host) first
attempts to fetch a fresh copy of XO Lite from `https://lite.xen-orchestra.com`
on every page load, using the locally-installed version only as a fallback.
This community build removes that remote fetch entirely. The locally-installed
version is always loaded directly.

```diff
-        try {
-          const response = await fetch('https://lite.xen-orchestra.com/dist/index.html')
-          ...
-          document.write(await response.text())
-          ...
-        } catch (err) {
-          console.log(err?.message ?? err)
-          // Fallback to local version of XO Lite
           document.open()
           document.write(await (await fetch('./xolite.html')).text())
           document.close()
-        }
```

**Why:** Eliminates the dependency on an external Vates-controlled CDN.
The community image is self-contained and air-gap friendly.

---

### Change 2 — Point "Deploy XOA" at the community image server

**File:** `@xen-orchestra/lite/src/pages/xoa-deploy.vue`

The official deploy page calls `VM.import` with a hardcoded URL pointing to
`http://xoa.io/xva` — Vates's proprietary appliance. This build replaces that
URL with the community image server.

```diff
-        'http://xoa.io/xva',
+        'http://192.168.0.1:3000/image.xva',
```

A defensive guard is also added around the VIF teardown step. The upstream
code unconditionally calls `VIF.destroy` on the first VIF returned by
`VM.get_VIFs`. If the imported XVA happens to have no VIFs baked in, that
call fails with a XAPI error and aborts the deploy. The patch makes the
destroy conditional:

```diff
-    await xapi.call('VIF.destroy', [vifRef])
+    if (vifRef !== undefined) {
+      await xapi.call('VIF.destroy', [vifRef])
+    }
```

**Why:** The community XVA is served from a local HTTP server
(`192.168.0.1:3000`) that is assumed to be reachable during installation.
The VIF guard prevents a crash on XVAs with no pre-existing network interface.

> **Note:** The XVA image URL is currently hardcoded. A planned improvement
> is to fetch the URL at runtime from
> `https://xo-image.yawn.fi/downloads/image.txt` so the image can be updated
> without rebuilding the ISO.

---

## Workflow walkthrough (`community-xoa-deploy.yml`)

The workflow runs on `ubuntu-latest` (GitHub Actions free tier) and produces
a bootable hybrid ISO published as a GitHub Release.

### Triggers

- Push to `patchxolite`
- `workflow_dispatch` with an optional `release_tag` input
  (e.g. `8.3.0-community-20260406`)

### Step-by-step

#### Step 0 — Checkout
Checks out this repository (the `patchxolite` branch).

#### Step 1 — Install system tools
```
xorriso  genisoimage  isomd5sum
rpm2cpio  cpio  rpm  syslinux-utils
createrepo-c
```
All standard Ubuntu packages. No custom PPAs or containers.

#### Step 2 — Download the official ISO
Downloads `xcp-ng-8.3.0-20250606.2.iso` from the official XCP-ng mirror
(`mirrors.xcp-ng.org`) and extracts it into `iso-work/`.

#### Step 3 — Detect XO Lite version
Finds the `xo-lite-*.rpm` file inside `iso-work/Packages/` and extracts its
version string using `rpm -qp --queryformat`. This value is stored as
`steps.xo-version.outputs.version` and used throughout later steps,
**avoiding any hardcoded version number** in the workflow.

#### Step 4 — Clone `vatesfr/xen-orchestra`
Clones the upstream monorepo at HEAD of the default branch. The patch is
applied at this point rather than checked in as a separate fork, keeping the
build reproducible from a known upstream state.

#### Step 5 — Apply the community patch
```bash
git apply $GITHUB_WORKSPACE/patches/community-xoa-deploy.patch
```
The patch file (`patches/community-xoa-deploy.patch`) is the single source
of truth for all XO Lite modifications. It targets two files:
- `@xen-orchestra/lite/scripts/xolite-loader.html`
- `@xen-orchestra/lite/src/pages/xoa-deploy.vue`

#### Step 6 — Node.js + Yarn
Sets up Node 22.3 via `actions/setup-node` and enables Corepack so that the
exact Yarn version declared in the monorepo's `packageManager` field is used
(`yarn.lock` is cached between runs).

#### Step 7 — Install dependencies and build
```bash
yarn install --frozen-lockfile
TURBO_TELEMETRY_DISABLED=1 yarn build:xo-lite
```
Builds only the `@xen-orchestra/lite` package using the monorepo's Turbo
pipeline. The `TURBO_TELEMETRY_DISABLED=1` flag suppresses CI noise from
telemetry prompts.

The build is verified: the workflow fails immediately if `dist/index.html` or
`dist/assets/` are missing.

#### Step 8 — Verify patch in built output
Three grep checks run against `dist/`:

| Check | Expected result |
|---|---|
| `xoa.io` present | ❌ FAIL |
| `lite.xen-orchestra.com` present | ❌ FAIL |
| `:3000` (community server) present | ✅ PASS |

This catches cases where the patch applied cleanly but Vite's bundler
tree-shook or inlined something unexpectedly.

#### Step 9 — Package tarball for rpmbuild
Assembles a `xo-lite-<VERSION>/` directory that mirrors the layout expected
by the upstream RPM spec:

| Source | Destination in tarball |
|---|---|
| `dist/*` | `.` (root) |
| `scripts/xolite-loader.html` | `xolite.html` |
| `CHANGELOG.md` | `CHANGELOG.md` |
| `LICENSE` / `LICENSE.md` | `LICENSE` |

The presence of every file declared in the RPM spec `%files` section is
asserted before `tar -czf` runs.

#### Step 10 — Build the RPM
`rpmbuild -ba` builds the RPM from `SPECS/xo-lite-community.spec`.
The spec version is injected at build time via `sed` so it always matches
what was detected from the ISO in Step 3.

Key facts about the spec:

- **Name:** `xo-lite` (same as the official package — intentionally, so it
  replaces it without leaving the old one installed)
- **Release tag:** `1.0.community.1` — identifies this as a community build
  in `rpm -qi` output
- **Install path:** `/opt/xensource/www/` — identical to the official package
- **License / doc files** are excluded from `/opt/xensource/www/` but
  correctly declared in `%license` / `%doc` so RPM bookkeeping is intact

#### Step 11 — Swap the RPM in the ISO
The original `xo-lite-*.rpm` is removed from `iso-work/Packages/` and
replaced with the freshly built community RPM.

#### Step 12 — Patch `isolinux.cfg`
The boot menu entry is extended with an answerfile pointer and `install` flag:

```
Before: --- /install.img
After:  answerfile=http://192.168.0.1:3000/answerfile.xml install --- /install.img
```

This enables unattended installation when an answerfile HTTP server is
reachable at `192.168.0.1:3000` during boot. **If no server is present the
installer falls back to interactive mode** (the parameter is simply ignored
when the URL is unreachable — standard XCP-ng installer behaviour).

#### Step 13 — Regenerate repo metadata
```bash
createrepo_c --update iso-work/
```
Updates `repodata/` so the installer's built-in yum resolver sees the
community RPM instead of the original one and does not complain about
checksum mismatches.

#### Step 14 — Repack ISO
Produces a bootable hybrid ISO using `xorriso`:
- Extracts the original MBR bytes (`dd bs=1 count=432`)
- Preserves dual BIOS + UEFI boot (`-b isolinux.bin` + `-e efiboot.img`)
- Sets the volume label to `XCP-ng ce`
- Runs `isohybrid --uefi` for USB-stick compatibility
- Implants an MD5 checksum with `implantisomd5`

Output: `xcp-ng-ce.iso`

#### Step 15 — Publish GitHub Release
Uses `softprops/action-gh-release@v2` to create a release tagged with
`${{ github.ref_name }}` and attaches `xcp-ng-ce.iso` as the release asset.
The release notes summarise what is different from the official ISO.

---

## Known issues and future work

### VIF / network selection bug in `xoa-deploy.vue`
`filteredNetworks` in the deploy page sorts all networks alphabetically.
On a freshly installed XCP-ng host the first alphabetical entry is often
**"Host internal management network"** (a non-routable internal bridge) rather
than the physical `eth0`-backed network. `useFormSelect` auto-selects the
first entry, so users who do not notice this will deploy XOA on the wrong
network.

Two remediation paths are tracked:

1. **Filter before sort** — exclude networks that have no associated PIF
   (i.e. no physical port) before sorting. The host internal management
   network has no PIF and would be removed automatically.
2. **Require explicit selection** — disable the Deploy button until the user
   has actively chosen a network, preventing silent auto-selection.

### XVA URL hardcoded
The community XVA URL (`http://192.168.0.1:3000/image.xva`) is currently
hardcoded in the patch. The intended architecture fetches the URL at runtime
from `https://xo-image.yawn.fi/downloads/image.txt`, which decouples ISO
rebuilds from image updates. This requires an additional `fetch` call in
`xoa-deploy.vue` before the `VM.import` call.

### `install.img` and answerfile injection
The XCP-ng installer's `install.img` is a **SquashFS** filesystem (not cpio).
If a locally-served answerfile is not viable in your environment, the
answerfile XML can be injected directly into `install.img`:

```bash
# Extract
unsquashfs -d installer-root iso-work/install.img

# Drop answerfile.xml into installer-root/
cp answerfile.xml installer-root/

# Repack (must match original compression settings)
sudo mksquashfs installer-root iso-work/install.img \
  -comp xz -b 131072 -noappend -no-progress
```

Then change the kernel parameter to `answerfile=file:///answerfile.xml`.
`file:///` resolves relative to the ramdisk root, not the ISO CD-ROM root.

---

## GPG notes

The community RPM is not GPG-signed. The XCP-ng installer enforces GPG
verification by default. If you inject an answerfile, include these attributes
on the `<installation>` tag to suppress the check:

```xml
<installation gpgcheck="false" repo-gpgcheck="false">
```

Both attributes must be set explicitly — each defaults to `True` independently.
This is not documented in the installer's `answerfile.txt`; it is only visible
in `answerfile.py` source.

---

## Keeping `master` in sync with upstream

```bash
# On master
git fetch upstream
git merge upstream/master   # or rebase — no local commits on master
git push origin master

# patchxolite is never rebased onto master automatically;
# the workflow always clones upstream fresh at workflow runtime.
```

The patch is applied to a fresh clone of `vatesfr/xen-orchestra` during every
CI run. If upstream renames or refactors the patched files the patch will
fail at Step 5 and the build will surface the conflict before a broken ISO is
published.
