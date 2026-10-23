"""Prepare a reversible native key-map experiment; never send game input.

The installed client attempts Controls/defaultProfile.xml during startup. Live
acceptance of console-command actions in that profile is still unverified.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

COMMANDS = (("r_DisplayInfo 1", "f14"), ("r_DisplayInfo 0", "f15"))


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_profile(source):
    """Retain the complete shipped profile and append only two command actions."""
    root = ET.fromstring(source)
    if root.tag != "profile" or root.find("platforms") is None:
        raise ValueError("Expected a complete native profile with platform definitions")
    target_maps = root.findall("./actionmap[@name='default']")
    if len(target_maps) != 1:
        raise ValueError("Expected exactly one default action map")
    reserved = {key for _, key in COMMANDS}
    names = {command for command, _ in COMMANDS}
    for action in root.iter("action"):
        if action.get("name") in names:
            raise ValueError("DisplayInfo command action already exists")
        for key, value in action.attrib.items():
            if key.lower() in {"keyboard", "input"}:
                tokens = {token.strip().lower() for token in value.replace("|", "+").split("+")}
                if reserved.intersection(tokens):
                    raise ValueError("F14/F15 is already bound in the source profile")
    original = deepcopy(root)
    for command, key in COMMANDS:
        ET.SubElement(target_maps[0], "action", {
            "name": command, "onPress": "1", "consoleCmd": "1",
            "noModifiers": "1", "keyboard": key,
        })
    # Check the whole tree, including platform/options/filter/activation data.
    audit = deepcopy(root)
    default = audit.find("./actionmap[@name='default']")
    for action in list(default):
        if action.get("name") in names:
            default.remove(action)
    if ET.tostring(audit) != ET.tostring(original):
        raise ValueError("Candidate changed an existing profile element")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def install_profile(candidate, manifest_path, game_root, *, game_running):
    """Create only the optional override, refusing collisions and running games."""
    if game_running:
        raise RuntimeError("Close Star Citizen before installing its startup profile")
    candidate = Path(candidate)
    manifest_path = Path(manifest_path)
    game_root = Path(game_root).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if sha256_file(game_root / "Bin64" / "StarCitizen.exe") != manifest["exe_sha256"]:
        raise RuntimeError("Game build changed; regenerate the profile from this build")
    if sha256_file(candidate) != manifest["candidate_sha256"]:
        raise RuntimeError("Candidate profile differs from its preparation manifest")
    # Keep existing per-player actionmaps.xml and USER.cfg separate and untouched.
    target = game_root / "USER" / "Client" / "0" / "Controls" / "defaultProfile.xml"
    if not target.parent.is_dir():
        raise RuntimeError("Expected existing game Controls directory was not found")
    if target.exists():
        raise FileExistsError("A custom defaultProfile.xml already exists; refusing to replace it")
    current = game_root / "USER" / "Client" / "0" / "Profiles" / "default" / "actionmaps.xml"
    if current.exists():
        root = ET.parse(current).getroot()
        for element in root.iter():
            for key, value in element.attrib.items():
                if key.lower() in {"keyboard", "input"}:
                    tokens = value.lower().replace("kb1_", "").replace("|", "+").split("+")
                    if {"f14", "f15"}.intersection(tokens):
                        raise RuntimeError("F14/F15 is already used by a personal binding")
    raw = candidate.read_bytes()
    state_path = manifest_path.parent / "installation.json"
    state = {"target": str(target), "candidate_sha256": manifest["candidate_sha256"],
             "status": "installed_unverified", "baseline_override_existed": False}
    # The state must be durable before creation so removal remains possible.
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    try:
        with target.open("xb") as stream:
            stream.write(raw)
    except FileExistsError:
        state_path.unlink(missing_ok=True)
        raise
    return state


def remove_profile(manifest_path, game_root, *, game_running):
    if game_running:
        raise RuntimeError("Close Star Citizen before removing its startup profile")
    state_path = Path(manifest_path).parent / "installation.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    expected = Path(game_root).resolve() / "USER" / "Client" / "0" / "Controls" / "defaultProfile.xml"
    if Path(state["target"]).resolve() != expected.resolve() or state["baseline_override_existed"]:
        raise RuntimeError("Installation record does not match the new optional override")
    if expected.exists():
        if sha256_file(expected) != state["candidate_sha256"]:
            raise RuntimeError("Custom profile changed since installation; leaving it in place")
        expected.unlink()
    state_path.unlink()
    return {"status": "removed", "target": str(expected)}
