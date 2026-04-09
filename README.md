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
`workflow_dispatch`). The `master` branch exists solely to stay in sync with
upstream.
---

## What this build changes

The official XCP-ng ISO ships a web application called **XO Lite** — a
lightweight Xen Orchestra UI served directly from the host at
`/opt/xensource/www/`. XO Lite includes a "Deploy XOA" page that downloads
and provisions a full Xen Orchestra (XVA).

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
The community image is self-contained.

---

### Change 2 — Point "Deploy XOA" at the community image server

**File:** `@xen-orchestra/lite/src/pages/xoa-deploy.vue`

The official deploy page calls `VM.import` with a hardcoded URL pointing to
`http://xoa.io/xva` — Vates's version of XOA. This build replaces that
URL with the community image server.

```diff
-        'http://xoa.io/xva',
+        'http://192.168.0.1:3000/image.xva',
```

At the VIF creation step, the upstream
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

**Why:** 
The check on VIF existence prevents a crash on XVAs with no pre-existing network interface.

> **Note:** The XVA image URL is currently hardcoded. A planned improvement
> is to be able to enter the URL in the XO-lite UI if different from the default one.

---

## Workflow walkthrough (`community-xoa-deploy.yml`)

The workflow runs on GitHub Actions and produces
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
Clones the upstream repo. The patch is applied at this point.

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
exact Yarn version declared in the repo's `packageManager` field is used
(`yarn.lock` is cached between runs).

#### Step 7 — Install dependencies and build
```bash
yarn install --frozen-lockfile
TURBO_TELEMETRY_DISABLED=1 yarn build:xo-lite
```
Builds only the `@xen-orchestra/lite` package using the repo's Turbo
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
This is a workaround currently to be able to skip GPG checks which are
failing after ISO repacking. This is expected to be a step removed
when the GPG check will be restored/fix.

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

### VIF / network selection issue in `xoa-deploy.vue`
`filteredNetworks` in the deploy page sorts all networks alphabetically.
On a freshly installed XCP-ng host the first alphabetical entry is time to time 
**"Host internal management network"** (a non-routable internal bridge) rather
than the physical `eth0`-backed network. `useFormSelect` auto-selects the
first entry, so users who do not notice this will deploy XOA on the wrong
network.
This issue is happens because i'm using Ronivay's image which doesn't get 
the interface provided when specifying it in XOLITE UI.

Remediation paths are tracked:

1. **Filter before sort** — exclude networks that have no associated PIF
   (i.e. no physical port) before sorting. The host internal management
   network has no PIF and would be removed automatically.
2. **Require explicit selection** — disable the Deploy button until the user
   has actively chosen a network, preventing silent auto-selection.
3. Recreate Ronivay's image that will be compatible with XO-LITE, I think it
   should be design to retreive the configuration, but have no idea how to
   do that yet

### Login/Pass
The default login and pass are the one set by Ronivay's image for now.
Same as the about should get the one set by the user in XO-lite deploy UI.

login: admin@admin.net
pass: admin

It must be changed at first login !


### XVA URL hardcoded
The community XVA URL is currently hardcoded in the patch.
The intended architecture is to configure have this link configurable 
which facilitate ISO and provide more flexibility to the user.

---

## GPG notes - workaround to avoid install failure

The community RPM is not GPG-signed. Because the ISO repacking seems to brake it at least in 
my experience. The XCP-ng installer enforces GPG verification by default. 
To disable this behaviour an answerfile, include these attributes
on the `<installation>` tag to suppress the check:

```xml
<installation gpgcheck="false" repo-gpgcheck="false">
```

Both attributes must be set explicitly — each defaults to `True` independently.

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
