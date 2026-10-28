#!/usr/bin/env zsh
setopt extended_glob

if (( $# < 1 || $# > 2 )); then
  print -u2 "Usage: ${0:t} <directory> [prefix]"
  print -u2 "  prefix defaults to the directory name before '_Sheet'"
  exit 1
fi

dir=${1:a}
if [[ ! -d $dir ]]; then
  print -u2 "Directory not found: $1"
  exit 1
fi

if (( $# == 2 )); then
  prefix=$2
else
  dirname=${dir:t}
  prefix=${dirname%%_Sheet}
  if [[ $prefix == $dirname || -z $prefix ]]; then
    print -u2 "Cannot infer prefix from directory name: $dirname"
    print -u2 "Usage: ${0:t} <directory> <prefix>"
    exit 1
  fi
fi

files=("$dir"/"$prefix"[0-9]##_*(N))
if (( ${#files} == 0 )); then
  print -r -- "No ${prefix}<sheet>_* files found in $dir"
  exit 0
fi

typeset -i renamed=0 skipped=0
answer=

for f in "${files[@]}"; do
  base=${f:t}
  rest=${base#$prefix}
  rest=${rest#[0-9]##_}
  new="$dir/${prefix}_${rest}"

  if [[ -e $new ]]; then
    print -r -- "SKIP (already exists): ${new:t}"
    (( skipped += 1 ))
    continue
  fi

  if [[ $answer != a ]]; then
    print
    if ! read -r "answer?${base} -> ${new:t}  [y]es/[N]o/[a]ll/[q]uit: "; then
      print
      break
    fi

    case $answer in
      y|Y) ;;
      a|A) answer=a ;;
      q|Q)
        print -r -- "Stopped."
        break
        ;;
      *)
        print -r -- "Skipped."
        (( skipped += 1 ))
        continue
        ;;
    esac
  fi

  if mv -- "$f" "$new"; then
    print -r -- "RENAMED: $base -> ${new:t}"
    (( renamed += 1 ))
  else
    print -u2 "FAILED: $base"
    (( skipped += 1 ))
  fi
done

print -r -- "Done: $renamed renamed, $skipped skipped."
