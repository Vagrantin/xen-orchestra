#!/bin/bash

# Replace the upgrade card render with null
python3 -c "
import re, sys

path = 'packages/xo-web/src/common/xoa-upgrade.js'
content = open(path).read()

# Replace the ternary upgrade card block with null
content = re.sub(
    r'process\.env\.XOA_PLAN < required \?.*?\) : children',
    'null',
    content,
    flags=re.DOTALL
)

open(path, 'w').write(content)
print('Patched xoa-upgrade.js')
"

FILES=(
  "packages/xo-web/src/xo-app/host/tab-patches.js"
  "packages/xo-web/src/xo-app/settings/ips/index.js"
  "packages/xo-web/src/xo-app/jobs/overview/index.js"
  "packages/xo-web/src/xo-app/jobs/schedules/index.js"
  "packages/xo-web/src/xo-app/jobs/new/index.js"
)

for f in "${FILES[@]}"; do
  python3 -c "
import re, sys

path = '$f'
content = open(path).read()

# Pattern: plan < N ? <UpgradeBlock> : <Feature>  →  null ? <UpgradeBlock> : <Feature>
# With plan=1 baked in, null replaces the upgrade block entirely
content = re.sub(
    r'(process\.env\.XOA_PLAN\s*[<>]=?\s*\d+\s*\?)\s*\([^)]*\)',
    r'null',
    content
)

open(path, 'w').write(content)
print('Patched $f')
"
done


# Buttons with disabled={XOA_PLAN.value < ENTERPRISE.value}
# Wrap them in a conditional so they don't render at all
for f in \
  "packages/xo-web/src/xo-app/vm/tab-advanced.js" \
  "packages/xo-web/src/xo-app/new-vm/index.js"; do

  sed -i "s/disabled={XOA_PLAN\.value < ENTERPRISE\.value}/style={{display: 'none'}}/" $f
done
