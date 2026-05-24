#!/bin/bash

BASE=packages/xo-web/src

# Find menu entries for these items
grep -n 'hub\|xostor\|proxies\|xoa\b' \
  $BASE/xo-app/menu/index.js \
  --include="*.js" -i | grep -v '//'

# Find the Hub page
find $BASE -path "*/hub*" -name "*.js" | head -20

# Find XOSTOR page
find $BASE -path "*/xostor*" -name "*.js" | head -20

# Find Proxies deploy button
grep -n 'deploy\|Deploy' $BASE/xo-app/proxies/index.js | head -20

# Find XOA menu section
grep -n 'xoa\|update\|license\|support\|notification' \
  $BASE/xo-app/menu/index.js -i | head -30
