#!/usr/bin/env bash
set -euo pipefail

mode="local"
dev_mode=0
force=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --local)
      mode="local"
      ;;
    --global)
      mode="global"
      ;;
    --dev)
      dev_mode=1
      ;;
    --force)
      force=1
      ;;
    --help|-h)
      cat <<'EOF'
Usage: install.sh [--global] [--dev] [--force]

Default:
  install.sh
  -> local release install into the current project

Modes:
  --global  install into $HOME
  --dev     clone with git and symlink for continuous development
  --force   replace conflicting reasflow-codex targets
EOF
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 1
      ;;
  esac
  shift
done

repo="${REASFLOW_DEV_REPO:-pkumelon/reasflow-codex}"
ref="${REASFLOW_DEV_REF:-main}"
source_override="${REASFLOW_DEV_SOURCE_DIR:-}"

if [ "$mode" = "global" ]; then
  target_root="$HOME"
  state_dir="${REASFLOW_DEV_STATE_DIR:-$HOME/.local/share/reasflow-dev}"
else
  target_root="$PWD"
  state_dir="${REASFLOW_DEV_STATE_DIR:-$target_root/.reasflow-dev}"
fi

agents_dir="$target_root/.codex/agents"
skills_dir="$target_root/.agents/skills"
private_skills_dir="$target_root/.codex/reasflow-skills"
manifest="$state_dir/manifest.txt"

tmp_dir="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing required command: $1" >&2
    exit 1
  }
}

download_to() {
  url="$1"
  dest="$2"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url" -o "$dest"
    return
  fi
  if command -v wget >/dev/null 2>&1; then
    wget -qO "$dest" "$url"
    return
  fi
  echo "curl or wget is required" >&2
  exit 1
}

remove_previous() {
  [ -f "$manifest" ] || return 0
  while IFS= read -r line; do
    case "$line" in
      FILE\ *)
        path="${line#FILE }"
        if [ -L "$path" ] || [ -f "$path" ]; then
          rm -f "$path"
        elif [ -d "$path" ]; then
          rm -rf "$path"
        fi
        ;;
    esac
  done < "$manifest"
}

ensure_clear_target() {
  path="$1"
  if [ -e "$path" ] || [ -L "$path" ]; then
    if [ "$force" -eq 1 ]; then
      rm -rf "$path"
    else
      echo "target already exists: $path" >&2
      echo "re-run with --force to replace it" >&2
      exit 1
    fi
  fi
}

mkdir -p "$agents_dir" "$skills_dir" "$private_skills_dir" "$state_dir"
remove_previous

if [ -n "$source_override" ]; then
  source_dir="$(cd "$source_override" && pwd)"
elif [ "$dev_mode" -eq 1 ]; then
  need_cmd git
  source_dir="$state_dir/source"
  if [ ! -d "$source_dir/.git" ]; then
    git clone "https://github.com/$repo.git" "$source_dir" >/dev/null 2>&1
  fi
  git -C "$source_dir" fetch --tags origin >/dev/null 2>&1
  git -C "$source_dir" checkout "$ref" >/dev/null 2>&1
  if git -C "$source_dir" rev-parse --verify "origin/$ref" >/dev/null 2>&1; then
    git -C "$source_dir" pull --ff-only origin "$ref" >/dev/null 2>&1
  fi
else
  need_cmd tar
  archive="$tmp_dir/reasflow-codex.tar.gz"
  download_to "https://codeload.github.com/$repo/tar.gz/$ref" "$archive"
  tar -xzf "$archive" -C "$tmp_dir"
  source_dir="$(find "$tmp_dir" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
fi

[ -d "$source_dir/skills" ] || {
  echo "invalid source: missing skills directory" >&2
  exit 1
}
[ -d "$source_dir/agents" ] || {
  echo "invalid source: missing agents directory" >&2
  exit 1
}

manifest_tmp="$tmp_dir/manifest.txt"
: > "$manifest_tmp"
printf 'MODE %s\n' "$( [ "$dev_mode" -eq 1 ] && echo dev || echo release )" >> "$manifest_tmp"
printf 'SCOPE %s\n' "$mode" >> "$manifest_tmp"
printf 'SOURCE %s\n' "$source_dir" >> "$manifest_tmp"

shared_root="$source_dir/skills/reasflow/shared"
if [ -d "$shared_root" ]; then
  find "$shared_root" -mindepth 1 -maxdepth 1 -type d | while IFS= read -r skill_root; do
    dest="$skills_dir/$(basename "$skill_root")"
    ensure_clear_target "$dest"
    if [ "$dev_mode" -eq 1 ]; then
      ln -s "$skill_root" "$dest"
    else
      cp -R "$skill_root" "$dest"
    fi
    printf 'FILE %s\n' "$dest" >> "$manifest_tmp"
  done
fi

find "$source_dir/skills/reasflow" -mindepth 1 -maxdepth 1 -type d | while IFS= read -r category_root; do
  category_name="$(basename "$category_root")"
  [ "$category_name" = "shared" ] && continue
  category_dest="$private_skills_dir/$category_name"
  mkdir -p "$category_dest"
  find "$category_root" -mindepth 1 -maxdepth 1 -type d | while IFS= read -r skill_root; do
    dest="$category_dest/$(basename "$skill_root")"
    ensure_clear_target "$dest"
    if [ "$dev_mode" -eq 1 ]; then
      ln -s "$skill_root" "$dest"
    else
      cp -R "$skill_root" "$dest"
    fi
    printf 'FILE %s\n' "$dest" >> "$manifest_tmp"
  done
done

for agent_path in "$source_dir"/agents/*.toml; do
  [ -f "$agent_path" ] || continue
  agent_name="$(basename "$agent_path")"
  dest="$agents_dir/$agent_name"
  ensure_clear_target "$dest"
  if [ "$dev_mode" -eq 1 ]; then
    ln -s "$agent_path" "$dest"
  else
    cp "$agent_path" "$dest"
  fi
  printf 'FILE %s\n' "$dest" >> "$manifest_tmp"
done

# Install project-level Codex config (orchestrator developer_instructions).
# Local install only: a global install would write into the user's personal
# ~/.codex/config.toml and clobber their model/provider/projects settings.
config_src="$source_dir/codex-config.toml"
config_installed=0
if [ "$mode" = "local" ] && [ -f "$config_src" ]; then
  config_dest="$target_root/.codex/config.toml"
  ensure_clear_target "$config_dest"
  if [ "$dev_mode" -eq 1 ]; then
    ln -s "$config_src" "$config_dest"
  else
    cp "$config_src" "$config_dest"
  fi
  printf 'FILE %s\n' "$config_dest" >> "$manifest_tmp"
  config_installed=1
elif [ "$mode" != "local" ]; then
  echo "  note: skipping .codex/config.toml on global install (install locally per project)" >&2
fi

cp "$manifest_tmp" "$manifest"

shared_skill_count="$(find -L "$skills_dir" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
private_skill_count="$(find -L "$private_skills_dir" -mindepth 2 -maxdepth 2 -type d | wc -l | tr -d ' ')"
agent_count="$(find -L "$agents_dir" -mindepth 1 -maxdepth 1 -type f -name '*.toml' | wc -l | tr -d ' ')"

echo "Installed reasflow-codex"
echo "  scope: $mode"
echo "  mode: $( [ "$dev_mode" -eq 1 ] && echo dev || echo release )"
echo "  shared skills: $shared_skill_count -> $skills_dir"
echo "  private skills: $private_skill_count -> $private_skills_dir"
echo "  agents: $agent_count -> $agents_dir"
if [ "$config_installed" -eq 1 ]; then
  echo "  config: -> $target_root/.codex/config.toml"
fi
echo "  manifest: $manifest"
