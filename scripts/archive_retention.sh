#!/usr/bin/env bash
# scripts/archive_retention.sh
#
# Shared logic for .github/workflows/archive.yml (the data-retention system).
# This file is the single source of truth for select/package/verify so that
# the workflow and the local dry-run exercise IDENTICAL code paths.
#
# Subcommands:
#   select   SRC_DIR DAYS [TODAY]
#       Print "<relpath>\t<YYYY-MM-DD>" (one per line, sorted) for every
#       directory under SRC_DIR whose basename matches YYYY-MM-DD and is
#       older than the retention window (i.e. NOT in the most recent DAYS
#       calendar days, inclusive of TODAY). Searches at any depth so it is
#       safe against both the flat `gha_data/<date>/...` layout and nested
#       layouts like `gha_data/metrics/<date>/`. Anything that doesn't match
#       the date-dir pattern (loose files, non-dated subdirs) is never
#       selected -- that is the safety rail against touching non-day data.
#
#   package  SRC_DIR OUT_DIR BRANCH_LABEL DAYS MAX_BYTES [TODAY]
#       Runs `select`, groups eligible day-dirs by YYYY-MM, greedily splits
#       each month into parts so the *uncompressed* byte budget per part
#       never exceeds MAX_BYTES (compression only shrinks further, so the
#       actual tar output is guaranteed <= MAX_BYTES for any non-adversarial
#       text/JSON data), builds one tar archive per part (zstd if available,
#       else gzip), self-verifies each archive immediately with
#       `verify-tar`, and writes OUT_DIR/manifest.tsv describing every part:
#         branch  month  part_num  tarfile  day_list  file_count  total_bytes  compressed_bytes  verify_status
#
#   verify-tar  TARFILE EXPECTED_FILE_COUNT EXPECTED_TOTAL_BYTES
#       Integrity-checks TARFILE (tar -t against the whole file, format
#       auto-detected from extension) and compares the archive's own entry
#       count + summed uncompressed member sizes (from `tar -tv`, no
#       extraction needed) against the expected values. Exits 0 and prints
#       "VERIFY_OK" on success, else exits 1 and prints "VERIFY_FAIL <why>".
#       This is called twice in production: once locally right after
#       packaging, and once again against the copy downloaded back from the
#       GitHub Release (the mandatory pre-prune gate).
#
set -euo pipefail

MAX_BYTES_DEFAULT=1932735283   # 1.8 GiB

log() { printf '[archive_retention] %s\n' "$*" >&2; }

# ---- date helpers -----------------------------------------------------

DATE_RE='^[0-9]{4}-[0-9]{2}-[0-9]{2}$'

# keep_from_date DAYS [TODAY] -> prints YYYY-MM-DD: the oldest date that is
# still inside the retention window. Dates strictly older are archived.
keep_from_date() {
  local days="$1" today="${2:-$(date -u +%F)}"
  date -u -d "${today} -$((days - 1)) days" +%F
}

# ---- select -------------------------------------------------------------

cmd_select() {
  local src_dir="$1" days="$2" today="${3:-$(date -u +%F)}"
  [ -d "$src_dir" ] || { log "select: no such dir: $src_dir"; return 1; }
  local keep_from
  keep_from="$(keep_from_date "$days" "$today")"
  log "select: today=$today retention_days=$days keep_from=$keep_from (dirs < keep_from are eligible)"

  find "$src_dir" -mindepth 1 -type d -regextype posix-extended \
      -regex '.*/[0-9]{4}-[0-9]{2}-[0-9]{2}' \
    | while IFS= read -r d; do
        local base
        base="$(basename "$d")"
        [[ "$base" =~ $DATE_RE ]] || continue
        if [[ "$base" < "$keep_from" ]]; then
          printf '%s\t%s\n' "$d" "$base"
        fi
      done \
    | sort -k2,2
}

# ---- package --------------------------------------------------------------

# byte_sum_and_count DIR -> prints "<file_count> <total_bytes>" for regular
# files under DIR (matches exactly what tar will store per-member).
byte_sum_and_count() {
  find "$1" -type f -printf '%s\n' | awk '{n++; s+=$1} END{printf "%d %d\n", n+0, s+0}'
}

cmd_package() {
  local src_dir="$1" out_dir="$2" branch_label="$3" days="$4" max_bytes="${5:-$MAX_BYTES_DEFAULT}" today="${6:-$(date -u +%F)}"
  mkdir -p "$out_dir"
  local manifest="$out_dir/manifest.tsv"
  : > "$manifest"
  printf 'branch\tmonth\tpart_num\ttarfile\tday_list\tfile_count\ttotal_bytes\tcompressed_bytes\tverify_status\n' >> "$manifest"

  local selected
  selected="$(cmd_select "$src_dir" "$days" "$today")"
  if [ -z "$selected" ]; then
    log "package: nothing eligible for archival (branch=$branch_label)"
    return 0
  fi

  local compressor ext
  if command -v zstd >/dev/null 2>&1; then
    compressor=zstd; ext=tar.zst
  else
    compressor=gzip; ext=tar.gz
  fi
  log "package: using compressor=$compressor ext=$ext"

  # group by month, preserving date order within a month
  local months
  months="$(printf '%s\n' "$selected" | awk -F'\t' '{print substr($2,1,7)}' | sort -u)"

  local month
  for month in $months; do
    local -a dirs=() dates=()
    while IFS=$'\t' read -r path date; do
      [[ "$date" == "$month"* ]] || continue
      dirs+=("$path"); dates+=("$date")
    done <<< "$selected"

    local part_num=1
    local -a part_dirs=() part_dates=()
    local part_bytes=0

    flush_part() {
      [ "${#part_dirs[@]}" -gt 0 ] || return 0
      local tarfile="$out_dir/${branch_label}_${month}_part${part_num}.${ext}"
      local flist
      flist="$(mktemp)"
      printf '%s\n' "${part_dirs[@]}" >> "$flist"

      if [ -f "$tarfile" ]; then
        log "package: $tarfile already exists -- skipping build (idempotent)"
      else
        log "package: building $tarfile (${#part_dirs[@]} day-dirs, ${part_bytes} raw bytes)"
        local tmp_tar="${tarfile}.building"
        if [ "$compressor" = zstd ]; then
          tar --zstd -cf "$tmp_tar" --files-from="$flist" \
            --transform "s#^$(printf '%s' "$src_dir" | sed 's/[.[\*^$/]/\\&/g')#gha_data#"
        else
          tar -czf "$tmp_tar" --files-from="$flist" \
            --transform "s#^$(printf '%s' "$src_dir" | sed 's/[.[\*^$/]/\\&/g')#gha_data#"
        fi
        mv "$tmp_tar" "$tarfile"
      fi
      rm -f "$flist"

      local expect_count=0 expect_bytes=0
      local d
      for d in "${part_dirs[@]}"; do
        read -r c b <<< "$(byte_sum_and_count "$d")"
        expect_count=$((expect_count + c))
        expect_bytes=$((expect_bytes + b))
      done

      local status
      if cmd_verify_tar "$tarfile" "$expect_count" "$expect_bytes"; then
        status="OK"
      else
        status="FAIL"
      fi

      local compressed_bytes
      compressed_bytes="$(stat -c%s "$tarfile" 2>/dev/null || stat -f%z "$tarfile")"
      if [ "$compressed_bytes" -gt "$max_bytes" ]; then
        log "package: WARNING $tarfile is ${compressed_bytes} bytes > MAX_BYTES=${max_bytes} (single day-dir too large to split further)"
        status="${status}_OVERSIZE"
      fi

      printf '%s\t%s\t%s\t%s\t%s\t%d\t%d\t%d\t%s\n' \
        "$branch_label" "$month" "$part_num" "$(basename "$tarfile")" \
        "$(IFS=,; echo "${part_dates[*]}")" "$expect_count" "$expect_bytes" "$compressed_bytes" "$status" \
        >> "$manifest"

      part_num=$((part_num + 1))
      part_dirs=(); part_dates=(); part_bytes=0
    }

    local i
    for i in "${!dirs[@]}"; do
      local d="${dirs[$i]}" dt="${dates[$i]}"
      read -r _c b <<< "$(byte_sum_and_count "$d")"
      if [ "${#part_dirs[@]}" -gt 0 ] && [ $((part_bytes + b)) -gt "$max_bytes" ]; then
        flush_part
      fi
      part_dirs+=("$d"); part_dates+=("$dt")
      part_bytes=$((part_bytes + b))
    done
    flush_part
  done

  log "package: manifest written to $manifest"
  cat "$manifest" >&2
}

# ---- verify-tar -----------------------------------------------------------

cmd_verify_tar() {
  local tarfile="$1" expect_count="$2" expect_bytes="$3"

  if [ ! -s "$tarfile" ]; then
    echo "VERIFY_FAIL empty-or-missing:$tarfile"; return 1
  fi

  local tar_flag
  case "$tarfile" in
    *.tar.zst) tar_flag="--zstd" ;;
    *.tar.gz)  tar_flag="-z" ;;
    *)         tar_flag="" ;;
  esac

  if ! tar $tar_flag -tf "$tarfile" > /dev/null 2>/tmp/verify_tar_err.$$; then
    echo "VERIFY_FAIL corrupt-archive:$(cat /tmp/verify_tar_err.$$ 2>/dev/null)"
    rm -f /tmp/verify_tar_err.$$
    return 1
  fi
  rm -f /tmp/verify_tar_err.$$

  local got_count got_bytes
  got_count="$(tar $tar_flag -tvf "$tarfile" | awk '$1 !~ /^d/' | wc -l)"
  got_bytes="$(tar $tar_flag -tvf "$tarfile" | awk '$1 !~ /^d/ {s+=$3} END{printf "%d", s+0}')"

  if [ "$got_count" -ne "$expect_count" ]; then
    echo "VERIFY_FAIL count-mismatch:got=$got_count expected=$expect_count"; return 1
  fi
  if [ "$got_bytes" -ne "$expect_bytes" ]; then
    echo "VERIFY_FAIL bytes-mismatch:got=$got_bytes expected=$expect_bytes"; return 1
  fi

  echo "VERIFY_OK count=$got_count bytes=$got_bytes file=$tarfile"
  return 0
}

# ---- dispatch ---------------------------------------------------------

main() {
  local cmd="${1:-}"; shift || true
  case "$cmd" in
    select)      cmd_select "$@" ;;
    package)     cmd_package "$@" ;;
    verify-tar)  cmd_verify_tar "$@" ;;
    *)
      echo "usage: $0 {select|package|verify-tar} ..." >&2
      exit 2
      ;;
  esac
}

main "$@"
