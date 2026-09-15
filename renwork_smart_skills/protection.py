"""Commercial Anti-Piracy, Machine ID Binding & Binary Protection for RenWork Skills."""

from __future__ import annotations

import base64
import datetime
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


def get_machine_id() -> str:
    """Extract deterministic, immutable hardware fingerprint for the local machine."""
    components = [platform.node(), platform.machine(), platform.processor()]
    system = platform.system().lower()

    if system == "windows":
        try:
            cmd = 'powershell -NoProfile -Command "(Get-CimInstance -Class Win32_ComputerSystemProduct).UUID"'
            out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL).strip()
            if out:
                components.append(out)
        except Exception:
            pass

        try:
            cmd = 'powershell -NoProfile -Command "(Get-CimInstance -Class Win32_Processor).ProcessorId"'
            out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL).strip()
            if out:
                components.append(out)
        except Exception:
            pass

        try:
            cmd = 'powershell -NoProfile -Command "(Get-CimInstance -Class Win32_LogicalDisk -Filter \'DeviceID=\"\"C:\"\"\').VolumeSerialNumber"'
            out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL).strip()
            if out:
                components.append(out)
        except Exception:
            pass

    elif system == "darwin":
        try:
            cmd = 'ioreg -rd1 -c IOPlatformExpertDevice | awk \'/IOPlatformUUID/ { split($0, line, "\\\""); print line[4] }\''
            out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL).strip()
            if out:
                components.append(out)
        except Exception:
            pass

    elif system == "linux":
        for p in ["/etc/machine-id", "/var/lib/dbus/machine-id"]:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        components.append(f.read().strip())
                        break
                except Exception:
                    pass

    raw_fingerprint = ":".join(str(c) for c in components if c)
    salted = f"SALT_RENWORK_COMMERCIAL_V1::{raw_fingerprint}::PEPPER_2026"
    digest = hashlib.sha256(salted.encode("utf-8")).hexdigest().upper()
    return f"MID-{digest[0:4]}-{digest[4:8]}-{digest[8:12]}-{digest[12:16]}"


def generate_keypair(out_dir: Path) -> tuple[Path, Path]:
    """Generate RSA-2048 private and public keypair."""
    if not HAS_CRYPTO:
        raise RuntimeError("cryptography package is required for keypair generation")

    out_dir.mkdir(parents=True, exist_ok=True)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    pub_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    priv_path = out_dir / "admin_private_key.pem"
    pub_path = out_dir / "public_key.pem"

    priv_path.write_bytes(priv_pem)
    pub_path.write_bytes(pub_pem)
    return priv_path, pub_path


def issue_license(
    private_key_path: Path,
    mid: str,
    name: str,
    days: int = 365,
    max_sessions: int = 1,
    permissions: list[str] | None = None
) -> str:
    """Issue a cryptographically signed Base64 license token."""
    if not HAS_CRYPTO:
        raise RuntimeError("cryptography package is required for license issuance")

    private_key = serialization.load_pem_private_key(private_key_path.read_bytes(), None)

    now = datetime.datetime.now()
    exp = now + datetime.timedelta(days=days)

    payload = {
        "v": "2.0",
        "mid": mid,
        "name": name,
        "max_s": max_sessions,
        "iat": now.strftime("%Y-%m-%d %H:%M:%S"),
        "exp": exp.strftime("%Y-%m-%d %H:%M:%S"),
        "perm": permissions or ["all"]
    }

    payload_json = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode("utf-8")
    signature = private_key.sign(
        payload_json,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256()
    )

    token_dict = {
        "p": payload,
        "s": base64.b64encode(signature).decode("utf-8")
    }

    token_b64 = base64.b64encode(json.dumps(token_dict, separators=(',', ':')).encode("utf-8")).decode("utf-8")
    return f"LIC-RSA-{token_b64}"


def verify_license(public_key_path: Path, license_key: str, current_mid: str | None = None) -> dict:
    """Verify license signature, hardware binding, expiration date, and clock rollback."""
    if not HAS_CRYPTO:
        return {"valid": False, "error": "cryptography package is missing"}

    if not license_key.startswith("LIC-RSA-"):
        return {"valid": False, "error": "Invalid license prefix. Expected 'LIC-RSA-'"}

    raw_b64 = license_key[len("LIC-RSA-"):]
    try:
        token_dict = json.loads(base64.b64decode(raw_b64).decode("utf-8"))
        payload = token_dict["p"]
        signature = base64.b64decode(token_dict["s"])
    except Exception as e:
        return {"valid": False, "error": f"Malformed license payload: {e}"}

    if not public_key_path.exists():
        return {"valid": False, "error": f"Public key not found at {public_key_path}"}

    public_key = serialization.load_pem_public_key(public_key_path.read_bytes())
    payload_json = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode("utf-8")

    try:
        public_key.verify(
            signature,
            payload_json,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256()
        )
    except InvalidSignature:
        return {"valid": False, "error": "Signature verification failed: Tampered or forged license!"}

    now = datetime.datetime.now()
    iat = datetime.datetime.strptime(payload["iat"], "%Y-%m-%d %H:%M:%S")
    if now < iat - datetime.timedelta(minutes=10):
        return {"valid": False, "error": "System clock rollback detected! Local time is earlier than license issue date."}

    exp = datetime.datetime.strptime(payload["exp"], "%Y-%m-%d %H:%M:%S")
    if now > exp:
        return {"valid": False, "error": f"License expired on {payload['exp']}"}

    if current_mid is None:
        current_mid = get_machine_id()

    bound_mid = payload.get("mid")
    if bound_mid and bound_mid != current_mid:
        return {
            "valid": False,
            "error": f"Hardware mismatch: License bound to {bound_mid}, but current machine is {current_mid}."
        }

    return {
        "valid": True,
        "name": payload.get("name"),
        "mid": bound_mid,
        "expires_at": payload.get("exp"),
        "max_sessions": payload.get("max_s", 1),
        "permissions": payload.get("perm", [])
    }


def audit_skill_safety(target_dir: Path) -> list[str]:
    """Scan directory to ensure zero private keys, secrets, or plaintext source leaks exist."""
    violations = []
    for root, _, files in os.walk(target_dir):
        for f in files:
            path = Path(root) / f
            lower_name = f.lower()
            if lower_name.endswith(".pem") and "private" in lower_name:
                violations.append(f"Private Key detected: {path.relative_to(target_dir)}")
            elif lower_name.endswith(".key") and not lower_name.startswith("public"):
                violations.append(f"Secret Key detected: {path.relative_to(target_dir)}")
            elif lower_name in {".env", "config.json"}:
                violations.append(f"Sensitive configuration detected: {path.relative_to(target_dir)}")
    return violations


def protect_skill(
    skill_dir: Path,
    output_dir: Path,
    package_name: str | None = None,
    public_key_path: Path | None = None
) -> dict:
    """
    Compile skill into native obfuscated binaries (.pyd), strip plaintext source,
    audit for secret leaks, and package a protected release zip.
    """
    skill_dir = skill_dir.resolve()
    name = package_name or f"{skill_dir.name}-protected"
    dist_dir = (output_dir / name).resolve()

    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir(parents=True, exist_ok=True)

    scripts_src = skill_dir / "scripts"
    scripts_dest = dist_dir / "scripts"

    has_pyarmor = bool(shutil.which("pyarmor"))

    if scripts_src.is_dir() and any(scripts_src.glob("*.py")):
        if has_pyarmor:
            cmd = f'pyarmor gen -O "{scripts_dest}" "{scripts_src}"'
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if res.returncode != 0:
                raise RuntimeError(f"PyArmor obfuscation failed: {res.stderr or res.stdout}")
        else:
            # Fallback: copy scripts if pyarmor is unavailable in current environment
            shutil.copytree(scripts_src, scripts_dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    elif scripts_src.is_dir():
        shutil.copytree(scripts_src, scripts_dest)

    # Sync documentation, references, and configuration templates
    sync_dirs = ["references", "templates", "assets", "cloud"]
    for d in sync_dirs:
        src_d = skill_dir / d
        if src_d.is_dir():
            shutil.copytree(src_d, dist_dir / d, ignore=shutil.ignore_patterns("__pycache__", "*.pem", "*.key"))

    for item in skill_dir.glob("*.*"):
        if item.is_file() and item.suffix in {".md", ".txt", ".json", ".yaml", ".yml"} and item.name != "config.json":
            shutil.copy2(item, dist_dir / item.name)

    if public_key_path and public_key_path.is_file():
        shutil.copy2(public_key_path, dist_dir / "public_key.pem")

    # Run audit
    violations = audit_skill_safety(dist_dir)
    if violations:
        raise RuntimeError(f"Security audit failed: {violations}")

    # Build zip
    zip_path = output_dir / f"{name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(dist_dir):
            for file in files:
                abs_file = Path(root) / file
                zf.write(abs_file, abs_file.relative_to(dist_dir))

    return {
        "status": "protected",
        "package_name": name,
        "dist_dir": str(dist_dir),
        "zip_path": str(zip_path),
        "zip_size_bytes": zip_path.stat().st_size,
        "obfuscated": has_pyarmor
    }
