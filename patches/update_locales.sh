jq -s '.[0] * .[1] | to_entries | sort_by(.key) | from_entries' \
  @xen-orchestra/web-core/lib/locales/en.json \
  patches/en-hl.json > temp.json && \
  mv temp.json @xen-orchestra/web-core/lib/locales/en.json
