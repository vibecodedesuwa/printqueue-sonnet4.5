"""Helpers for comparing identities reported by AD, OIDC, and CUPS."""


def username_aliases(value, domain=None):
    """Return safe, case-insensitive aliases for an account name.

    CUPS clients commonly report ``DOMAIN\\user`` or ``user@domain`` while
    LDAP/OIDC normally reports ``user``.  The local-part UPN alias is only
    added when it belongs to the configured AD domain, avoiding accidental
    matches between unrelated domains.
    """
    if not isinstance(value, str):
        return set()

    raw = value.strip().casefold()
    if not raw:
        return set()

    aliases = {raw}
    if "\\" in raw:
        local = raw.rsplit("\\", 1)[-1].strip()
        if local:
            aliases.add(local)

    if "@" in raw:
        local, suffix = raw.rsplit("@", 1)
        configured_domain = (domain or "").strip().casefold()
        if local and configured_domain and suffix == configured_domain:
            aliases.add(local)

    return aliases


def usernames_match(left, right, domain=None):
    """Return whether two identity spellings refer to the same account."""
    left_aliases = username_aliases(left, domain=domain)
    right_aliases = username_aliases(right, domain=domain)
    return bool(left_aliases and right_aliases and left_aliases & right_aliases)


def canonical_username(value, domain=None):
    """Return the preferred stable form of an AD-style username."""
    aliases = username_aliases(value, domain=domain)
    if not aliases:
        return ""
    raw = value.strip().casefold()
    local_aliases = [alias for alias in aliases if "\\" not in alias and "@" not in alias]
    return local_aliases[0] if local_aliases else raw
