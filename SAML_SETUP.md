# SAML SSO Setup Guide for Jabber4Linux

This guide explains how to configure and use SAML Single Sign-On (SSO) authentication with Jabber4Linux.

## Overview

Jabber4Linux now supports SAML SSO authentication in addition to traditional username/password authentication. This allows you to authenticate against identity providers like Keycloak, Azure AD, Okta, or ADFS instead of providing credentials directly to CUCM.

## Architecture

The SAML authentication flow works as follows:

```
1. User selects "SAML SSO" in Jabber4Linux login window
2. Jabber4Linux opens embedded browser pointing to CUCM SAML login URL
3. CUCM redirects to your Identity Provider (IdP) - e.g., Keycloak
4. User authenticates with IdP credentials
5. IdP sends SAML assertion back to CUCM
6. CUCM validates assertion and creates session cookies
7. Jabber4Linux captures cookies and uses them for UDS API calls
8. User is logged in without providing password to Jabber4Linux
```

## Prerequisites

### 1. CUCM Configuration

Your Cisco Unified Communications Manager must be configured for SAML SSO:

- **CUCM Version**: 10.0 or higher
- **SAML SSO**: Configured and enabled
- **IdP**: Configured (Keycloak, Azure AD, ADFS, Okta, etc.)
- **Circle of Trust**: Established between CUCM (SP) and IdP

#### CUCM Configuration Steps:

1. Navigate to CUCM Admin > User Management > User Settings > SAML Single Sign-On
2. Enable SAML SSO
3. Import your IdP metadata
4. Configure SSO test URL
5. Test SSO authentication
6. Enable SSO for Jabber

Refer to Cisco documentation:
- [SAML SSO Deployment Guide for CUCM](https://www.cisco.com/c/en/us/td/docs/voice_ip_comm/cucm/SAML_SSO_deployment_guide/12_5_1/cucm_b_saml-sso-deployment-guide-12_5.html)

### 2. Keycloak Configuration

If using Keycloak as your IdP:

1. Create a new Client in Keycloak for CUCM
2. Set Client Protocol to `saml`
3. Configure Valid Redirect URIs: `https://CUCM_SERVER:8443/*`
4. Set up user attributes (uid must match LDAP user ID)
5. Export SAML metadata and import to CUCM

### 3. Python Dependencies

Install required Python packages:

```bash
# For embedded web browser (SAML authentication)
pip install PyQt6-WebEngine

# Already required by Jabber4Linux:
# - PyQt6
# - requests
```

## Using SAML Authentication

### First Time Setup

1. Start Jabber4Linux
2. In the login window:
   - Enter your **CUCM server address** and **port** (default: 8443)
   - Select **"SAML SSO"** radio button
   - Click **"Login with SAML"**

3. A browser window opens:
   - You'll be redirected to your Identity Provider (Keycloak)
   - Log in with your IdP credentials
   - After successful authentication, you'll be redirected back to CUCM
   - The browser window closes automatically

4. If prompted, enter your **username** (needed for device configuration)

5. Jabber4Linux completes login and retrieves your device configuration

### Configuration File

After successful SAML login, your session information is saved in:
```
~/.config/jabber4linux/settings.json
```

The configuration includes:
- CUCM server address and port
- User details (from UDS API)
- Device configuration
- Session preferences

**Note**: SAML session cookies are **not** stored permanently for security reasons. You'll need to re-authenticate when cookies expire or after restart.

## Troubleshooting

### Problem: "No CUCM session cookies found"

**Cause**: The SAML authentication flow didn't complete successfully, or cookies were not captured.

**Solution**:
1. Verify CUCM SAML SSO is properly configured
2. Test CUCM SSO from a regular web browser: `https://CUCM_SERVER:8443/ssosp/saml/login`
3. Check browser console for errors (run Jabber4Linux with `--debug`)
4. Ensure your IdP is reachable and configured correctly

### Problem: "SSL Certificate Error"

**Cause**: Self-signed certificates or untrusted CAs.

**Solution**:
1. Export your CUCM and IdP certificates
2. Place them in: `~/.config/jabber4linux/server-certs/`
3. Jabber4Linux will automatically trust these certificates

### Problem: "Username required for device configuration"

**Cause**: SAML authentication succeeded, but Jabber4Linux needs your username for UDS API queries.

**Solution**:
- Enter your username when prompted (same as your LDAP user ID)
- Future enhancement: Extract username from SAML assertion automatically

### Debug Mode

Run Jabber4Linux in debug mode to see detailed SAML flow:

```bash
python3 -m jabber4linux --debug
```

This prints:
- SAML login URL
- URL redirects during authentication
- Cookies received
- UDS API requests with authentication method

## Security Considerations

### Cookies and Session Management

- SAML session cookies are stored only in memory during runtime
- Cookies are not persisted to disk
- Session expires based on CUCM SAML session timeout (configurable in CUCM)
- You'll need to re-authenticate when:
  - Restarting Jabber4Linux
  - CUCM session expires
  - Cookies are invalidated

### Self-Signed Certificates

- Place trusted certificates in `~/.config/jabber4linux/server-certs/`
- **Warning**: The current implementation accepts self-signed certificates in the embedded browser
- For production, configure proper certificate validation

### Network Security

- SAML authentication requires HTTPS (port 8443 by default)
- Ensure firewall allows outbound connections to:
  - CUCM server (port 8443)
  - Identity Provider (typically port 443)

## Advantages of SAML SSO

1. **No Password in Jabber4Linux**: Your password never touches the application
2. **Single Sign-On**: Use your organization's IdP (same password as other services)
3. **Centralized Authentication**: IT controls authentication policies in IdP
4. **MFA Support**: If your IdP supports MFA, it works automatically
5. **Password Policies**: Enforced by IdP, not CUCM
6. **Audit Trail**: Authentication events logged in IdP

## Comparison: Basic Auth vs SAML

| Feature | Basic Auth | SAML SSO |
|---------|-----------|----------|
| Password handling | Sent to CUCM | Not sent to CUCM |
| Identity Provider | CUCM LDAP | Keycloak/Azure/ADFS/Okta |
| MFA Support | No | Yes (via IdP) |
| Session Management | Username/Password | Session Cookies |
| User Experience | Type credentials | Browser-based SSO |
| Setup Complexity | Simple | Requires CUCM+IdP config |

## Technical Details

### Authentication Methods in UdsWrapper

The `UdsWrapper` class now supports two authentication modes:

**Basic Authentication**:
```python
uds = UdsWrapper(
    username='jdoe',
    password='secret',
    serverName='cucm.example.com',
    serverPort='8443',
    trustedCerts=certs
)
```

**SAML Cookie-based Authentication**:
```python
uds = UdsWrapper(
    username='jdoe',
    password=None,
    serverName='cucm.example.com',
    serverPort='8443',
    trustedCerts=certs,
    saml_cookies={'JSESSIONID': 'abc123...', 'JSESSIONIDSSO': 'xyz789...'}
)
```

### SAML Login Flow (Code)

```python
from jabber4linux.SamlAuthClient import SamlAuthClient, SamlLoginWindow

# Create SAML client
saml_client = SamlAuthClient('cucm.example.com', '8443', debug=True)

# Open login window (embedded browser)
saml_window = SamlLoginWindow(saml_client)
if saml_window.exec() == QtWidgets.QDialog.DialogCode.Accepted:
    # Get session cookies
    cookies = saml_client.get_session_cookies()

    # Use cookies for UDS API
    uds = UdsWrapper(..., saml_cookies=cookies)
    user_details = uds.getUserDetails()
```

## Future Enhancements

Planned improvements for SAML support:

1. **Token Refresh**: Automatic SAML session refresh before expiry
2. **Username Extraction**: Parse SAML assertion to get username automatically
3. **Certificate Validation**: Proper SSL certificate validation in browser
4. **Persistent Sessions**: Optional secure storage of session tokens
5. **Kerberos Integration**: Windows domain single sign-on
6. **OAuth 2.0**: Support OAuth tokens in addition to SAML cookies

## References

- [Cisco SAML SSO Deployment Guide](https://www.cisco.com/c/en/us/td/docs/voice_ip_comm/cucm/SAML_SSO_deployment_guide/12_5_1/cucm_b_saml-sso-deployment-guide-12_5.html)
- [Enable SAML SSO for Jabber Clients](https://www.cisco.com/c/en/us/support/docs/unified-communications/jabber-windows/118774-configure-jabber-00.html)
- [Keycloak SAML Configuration](https://www.keycloak.org/docs/latest/server_admin/#_saml-clients)
- [Jabber4Linux GitHub](https://github.com/schorschii/Jabber4Linux)

## Support

For issues or questions:

1. Enable debug mode: `python3 -m jabber4linux --debug`
2. Check CUCM SAML SSO configuration
3. Verify IdP (Keycloak) configuration
4. Review logs for authentication errors
5. Open an issue on GitHub with debug output

## License

This SAML implementation is part of Jabber4Linux and follows the same GPL-3.0 license.
