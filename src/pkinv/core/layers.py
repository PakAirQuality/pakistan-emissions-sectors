"""Which repository holds a path: the public one, or the restricted layers beside it.

WHY THIS EXISTS. Through rc68 one private repository held everything: the code, the verified
tables and products, and some 6,000 third-party documents that cannot be republished (the
PBS household survey microdata among them). Each release was then COPIED to the public
repository without those documents (scripts/make_public_copy.py), so the public history was
one snapshot per release and every change was made somewhere a reader could not see.

From rc69 the work is committed in the public repository itself. The documents stay where
they were, in the private checkout, which is now only the RESTRICTED LAYERS: the trees and
files this module names. A public clone mounts them as symlinks (scripts/overlay.py), and
nothing that reads them changes, because the paths are the same. What does change is every
question put to GIT about them: `git ls-files sources` in the public clone returns nothing,
since git does not follow a symlink into another repository. So those questions go through
here, and are put to whichever repository owns the path.

FOUR MODES, ONE PREDICATE.
  monorepo  this checkout itself tracks the restricted layers (the private repository; the
            behaviour of every release through rc68).
  overlay   a public clone with the restricted layers mounted from the private checkout,
            named by $PKINV_OVERLAY or by the first line of the gitignored .pkinv-overlay.
  package   a built validation package (FILE_INVENTORY.csv at its root); tests/_support.py
            already decides document by document what such a package carries.
  absent    a public clone without the layers. The documents are not here by design.
present() is true in the first two. A guard that needs the documents asks it; it never
infers absence from an empty listing, because an empty listing is also what a broken mount
returns - the failure mode that has already made one guard of this project pass while
seeing nothing (tests/test_holdings_discipline.py, "a dead layer").

A CONFIGURED OVERLAY THAT DOES NOT RESOLVE IS AN ERROR, never "absent": absent mode skips
tests, and a mount that silently broke must not turn the restricted guards into skips.
"""
import fnmatch
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
CONFIG = ".pkinv-overlay"
ENVIRONMENT = "PKINV_OVERLAY"

# (prefix, what it is). Each names a whole tree; the public repository ignores the name
# itself (no trailing slash), because the mount is a symlink and git calls a symlink a file.
RESTRICTED_TREES = (
    ("sources", "primary documents (frozen legacy tree)"),
    ("data/raw", "primary documents and comparator datasets"),
    ("data/cache", "downloaded aircraft-position archives used by one pilot study"),
    ("data/nfdc", "third-party documents under an older path"),
    ("data/gleam", "third-party documents under an older path"),
    ("data/gmw", "third-party documents under an older path"),
    ("data/pbs_census", "third-party documents under an older path"),
    ("data/district_records", "third-party documents under an older path"),

    ("campaign", "working notes"),
    ("research_campaign", "working notes"),
    (".claude", "tool settings"),
)
# Third-party rasters, one by one: the folders they sit in also hold this project's own
# provenance notes (*SOURCES*.json), which are public. And the agent instructions, which are
# working notes about this machine rather than part of the release.
RESTRICTED_FILES = (
    ("data/shared/gis/worldpop_pak_2020_1km.tif", "third-party raster"),
    ("data/sectors/agriculture/gis/manual/gcd_rice_2023.tif", "third-party raster"),
    ("data/sectors/agriculture/gis/manual/spam2020_V2r2_global_A_RICE_I.tif",
     "third-party raster"),
    ("data/sectors/agriculture/gis/manual/spam2020_V2r2_global_A_RICE_R.tif",
     "third-party raster"),
    ("data/sectors/agriculture/gis/manual/spam_rice.tif", "third-party raster"),
    # the OCHA COD-AB boundaries (CC BY-IGO), held as documents; read by the ADM2 2022 frame
    # crosswalk only. Their provenance note COD_AB_SOURCES.json is this project's own and public.
    ("data/shared/gis/cod_ab/pak_admin2.geojson", "third-party boundary download"),
    ("data/shared/gis/cod_ab/pak_admin_boundaries.geojson.zip", "third-party boundary download"),
    ("CLAUDE.md", "working notes"),
)
RESTRICTED_PATTERNS = (
    # every GHSL tile, and no other file of that folder
    ("data/shared/gis/manual/ghsl_built_1km/*.tif", "third-party raster"),
)
# Record-level survey files are restricted wherever a future layout puts them.
FORBIDDEN_SUFFIXES = (".sav", ".dta", ".por", ".zsav")
# GitHub refuses a file over 100 MiB. Products above this size are this project's own; they
# are built, ignored by the public repository, and shipped in the deposit.
SIZE_LIMIT_BYTES = 95 * 1024 * 1024
TOO_LARGE = (
    "outputs/pakemis_ghg_configuration_adm2_monthly.csv",
    "outputs/semantic/fact_adm1_month.csv",
    "outputs/semantic/fact_adm2_month.csv",
)


class LayersError(RuntimeError):
    """The restricted layers are configured and cannot be reached."""


def restricted_reason(relative):
    """Why a repository-relative path belongs to the restricted layers, or None."""
    relative = relative.replace(os.sep, "/")
    if relative.startswith("./"):
        relative = relative[2:]
    for prefix, reason in RESTRICTED_TREES:
        if relative == prefix or relative.startswith(prefix + "/"):
            return reason
    for path, reason in RESTRICTED_FILES:
        if relative == path:
            return reason
    for pattern, reason in RESTRICTED_PATTERNS:
        if fnmatch.fnmatchcase(relative, pattern):
            return reason
    if relative.lower().endswith(FORBIDDEN_SUFFIXES):
        return "record-level survey file"
    return None


def is_restricted(relative):
    return restricted_reason(relative) is not None


def mounts():
    """Every restricted name a public clone links to the overlay: the trees, the named
    files, and the files the patterns match in the overlay. Paths relative to the root."""
    names = [prefix for prefix, _ in RESTRICTED_TREES] + [p for p, _ in RESTRICTED_FILES]
    overlay = overlay_root()
    if overlay and overlay != ROOT:
        for pattern, _ in RESTRICTED_PATTERNS:
            folder = os.path.dirname(pattern)
            base = os.path.join(overlay, folder)
            if os.path.isdir(base):
                names += sorted("%s/%s" % (folder, name) for name in os.listdir(base)
                                if fnmatch.fnmatchcase("%s/%s" % (folder, name), pattern))
    return names


def configured_overlay(root=ROOT):
    """The overlay path the environment or .pkinv-overlay names, unchecked, or None."""
    value = os.environ.get(ENVIRONMENT, "").strip()
    if not value:
        config = os.path.join(root, CONFIG)
        if os.path.isfile(config):
            with open(config, encoding="utf-8") as handle:
                lines = [l.strip() for l in handle if l.strip() and not l.startswith("#")]
            value = lines[0] if lines else ""
    return os.path.abspath(os.path.expanduser(value)) if value else None


def _tracks_sources(root):
    path = os.path.join(root, "sources")
    return os.path.isdir(path) and not os.path.islink(path) \
        and os.path.isdir(os.path.join(root, ".git"))


def overlay_root(root=ROOT):
    """The repository that owns the restricted layers: the overlay, this checkout itself in
    monorepo mode, or None when they are absent. Raises LayersError for a configured overlay
    that is not a checkout of them."""
    configured = configured_overlay(root)
    if configured:
        if not _tracks_sources(configured):
            raise LayersError("%s names %s as the restricted layers, and it is not a checkout "
                              "that tracks sources/" % (CONFIG, configured))
        return configured
    if _tracks_sources(root):
        return root
    return None


def mode(root=ROOT):
    if os.path.exists(os.path.join(root, "FILE_INVENTORY.csv")):
        return "package"
    overlay = overlay_root(root)
    if overlay is None:
        return "absent"
    if overlay == os.path.abspath(root):
        return "monorepo"
    broken = [name for name in (p for p, _ in RESTRICTED_TREES)
              if os.path.lexists(os.path.join(overlay, name))
              and not os.path.exists(os.path.join(root, name))]
    if broken:
        raise LayersError("the overlay %s is configured but not mounted here: %s. Run "
                          "python3 scripts/overlay.py link" % (overlay, ", ".join(broken)))
    return "overlay"


def present(root=ROOT):
    """True when the restricted layers can be read and asked about: monorepo or overlay."""
    return mode(root) in ("monorepo", "overlay")


# --- git, asked of the repository that owns the path ------------------------------------------

def _git(cwd, *args, text=True):
    run = subprocess.run(["git", "-C", cwd] + list(args), capture_output=True, text=text)
    return run


def _lines(cwd, *args):
    run = _git(cwd, *args)
    if run.returncode:
        return []
    return [line.strip() for line in run.stdout.splitlines() if line.strip()]


def repositories(root=ROOT):
    """(public root, overlay root) - the same path twice in monorepo mode; overlay None when
    the layers are absent."""
    try:
        overlay = overlay_root(root)
    except LayersError:
        overlay = None
    return os.path.abspath(root), overlay


def ls_files(*prefixes, root=ROOT):
    """Tracked paths, each from the repository that owns it. A restricted path counts only
    when the overlay tracks it; a non-restricted one only when this checkout does."""
    public, overlay = repositories(root)
    here = _lines(public, "ls-files", "--", *prefixes)
    if overlay is None or overlay == public:
        return here
    there = [p for p in _lines(overlay, "ls-files", "--", *prefixes) if is_restricted(p)]
    return sorted(set(p for p in here if not is_restricted(p)) | set(there))


def lfs_files(root=ROOT):
    """Paths stored in Git LFS, from both repositories; empty when git-lfs is unavailable."""
    public, overlay = repositories(root)
    found = set(_lines(public, "lfs", "ls-files", "-n"))
    if overlay and overlay != public:
        found = {p for p in found if not is_restricted(p)} | {
            p for p in _lines(overlay, "lfs", "ls-files", "-n") if is_restricted(p)}
    return found


def git_show(commit, path, root=ROOT):
    """The bytes `commit` held at `path`, from whichever repository holds that commit (the
    releases through rc68 exist only in the private history), or None."""
    public, overlay = repositories(root)
    for repo in (public, overlay):
        if not repo:
            continue
        run = _git(repo, "show", "%s:%s" % (commit, path), text=False)
        if run.returncode == 0:
            return run.stdout
        if repo == overlay:
            break
    return None


def history_repositories(root=ROOT):
    """The repositories whose history a ledger check must read: this one, then the overlay
    when it is a different repository."""
    public, overlay = repositories(root)
    return [public] + ([overlay] if overlay and overlay != public else [])


def head(repo):
    """(commit, dirty) of a checkout, or (None, None) outside one."""
    run = _git(repo, "rev-parse", "HEAD")
    if run.returncode:
        return None, None
    status = _git(repo, "status", "--porcelain")
    return run.stdout.strip(), bool(status.stdout.strip())


def describe(root=ROOT):
    """What a release record says about the restricted layers it was built with."""
    try:
        current = mode(root)
    except LayersError as error:
        return {"mode": "broken", "error": str(error)}
    if current not in ("overlay", "monorepo"):
        return {"mode": current, "commit": None, "dirty": None}
    commit, dirty = head(overlay_root(root))
    return {"mode": current, "commit": commit, "dirty": dirty}


if __name__ == "__main__":
    import json
    record = describe()
    record["overlay"] = configured_overlay()
    print(json.dumps(record, indent=1))
