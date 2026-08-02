"""
Active Directory / LDAP Authentication Module for Print Queue Manager
Supports LDAP authentication against Active Directory (AD) or OpenLDAP servers.
"""
import logging
import re
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

try:
    import ldap3
    from ldap3 import Server, Connection, ALL, NTLM, SIMPLE
    LDAP3_AVAILABLE = True
except ImportError:
    LDAP3_AVAILABLE = False


class ActiveDirectoryAuth:
    """Active Directory / LDAP Authentication Handler"""

    def __init__(self, config: dict):
        self.enabled = config.get('LDAP_ENABLED', False)
        self.host = config.get('LDAP_HOST', '')
        self.port = config.get('LDAP_PORT', 389)
        self.use_ssl = config.get('LDAP_USE_SSL', False)
        self.base_dn = config.get('LDAP_BASE_DN', '')
        self.bind_dn = config.get('LDAP_BIND_DN', '')
        self.bind_password = config.get('LDAP_BIND_PASSWORD', '')
        self.domain = config.get('LDAP_DOMAIN', '')
        self.user_search_filter = config.get(
            'LDAP_USER_SEARCH_FILTER',
            '(&(objectClass=user)(sAMAccountName={username}))'
        )

    def is_configured(self) -> bool:
        """Check if LDAP/AD is enabled and configured."""
        return self.enabled and bool(self.host) and LDAP3_AVAILABLE

    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate a user against Active Directory / LDAP.
        Returns user info dictionary if authentication succeeds, else None.
        """
        if not self.is_configured():
            logger.warning("[AD Auth] LDAP is not configured or ldap3 module is missing.")
            return None

        if not username or not password:
            return None

        username = username.strip()

        try:
            protocol = 'ldaps' if self.use_ssl else 'ldap'
            server_url = f"{protocol}://{self.host}:{self.port}"
            server = Server(server_url, get_info=ALL)

            # Determine bind format
            user_principal = username
            if self.domain and '@' not in username and '\\' not in username:
                user_principal = f"{username}@{self.domain}"

            # Step 1: Direct bind attempt with user credentials
            conn = Connection(
                server,
                user=user_principal,
                password=password,
                authentication=SIMPLE,
                auto_bind=False
            )

            if not conn.bind():
                # If direct bind failed and service bind DN is provided, try searching first
                if self.bind_dn and self.bind_password:
                    admin_conn = Connection(
                        server,
                        user=self.bind_dn,
                        password=self.bind_password,
                        authentication=SIMPLE,
                        auto_bind=True
                    )
                    search_filter = self.user_search_filter.format(username=username)
                    admin_conn.search(
                        search_base=self.base_dn,
                        search_filter=search_filter,
                        attributes=['dn', 'displayName', 'mail', 'memberOf', 'sAMAccountName', 'userPrincipalName']
                    )

                    if admin_conn.entries:
                        user_entry = admin_conn.entries[0]
                        user_dn = user_entry.entry_dn
                        # Retry bind with resolved user DN
                        conn = Connection(
                            server,
                            user=user_dn,
                            password=password,
                            authentication=SIMPLE,
                            auto_bind=False
                        )
                        if not conn.bind():
                            logger.info(f"[AD Auth] Authentication failed for user '{username}'")
                            return None
                    else:
                        logger.info(f"[AD Auth] User '{username}' not found in AD search")
                        return None
                else:
                    logger.info(f"[AD Auth] Direct bind failed for user '{username}'")
                    return None

            # User authenticated! Fetch user attributes and group memberships.
            search_filter = self.user_search_filter.format(username=username)
            if not self.base_dn and self.domain:
                # Construct base DN from domain (e.g. company.local -> DC=company,DC=local)
                self.base_dn = ','.join([f"DC={part}" for part in self.domain.split('.')])

            groups: List[str] = []
            display_name = username
            email = f"{username}@{self.domain}" if self.domain else ""

            if self.base_dn:
                conn.search(
                    search_base=self.base_dn,
                    search_filter=search_filter,
                    attributes=['displayName', 'mail', 'memberOf', 'cn', 'sAMAccountName']
                )

                if conn.entries:
                    entry = conn.entries[0]
                    if hasattr(entry, 'displayName') and entry.displayName:
                        display_name = str(entry.displayName)
                    if hasattr(entry, 'mail') and entry.mail:
                        email = str(entry.mail)

                    if hasattr(entry, 'memberOf') and entry.memberOf:
                        # Extract group CNs from memberOf DN strings
                        for group_dn in entry.memberOf:
                            match = re.search(r'CN=([^,]+)', str(group_dn), re.IGNORECASE)
                            if match:
                                groups.append(match.group(1))

            conn.unbind()

            user_info = {
                'username': username,
                'name': display_name,
                'email': email,
                'groups': groups,
                'auth_type': 'ad'
            }
            logger.info(f"[AD Auth] User '{username}' authenticated successfully via AD.")
            return user_info

        except Exception as e:
            logger.error(f"[AD Auth] Exception during authentication for '{username}': {e}")
            return None
