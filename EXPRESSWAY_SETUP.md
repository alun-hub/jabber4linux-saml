# Expressway-C Configuration for Jabber4Linux with SAML

This guide explains how to use Jabber4Linux with SAML SSO when connecting through Cisco Expressway-C (Mobile Remote Access).

## Architecture Overview

### Without Expressway (Internal Network)
```
Jabber4Linux → CUCM (direct) → Keycloak IdP
```

### With Expressway (External/MRA)
```
Jabber4Linux → Expressway-E (Edge) → Expressway-C (Core) → CUCM → Keycloak IdP
     (external)    (DMZ/internet)        (internal DMZ)      (internal)
```

## When to Use Expressway Mode

✅ **Use Expressway mode when:**
- You're connecting from outside the corporate network (home, remote office, etc.)
- Your organization uses Mobile Remote Access (MRA)
- DNS resolves to Expressway-E instead of CUCM
- You receive SSL certificates from Expressway, not CUCM directly

❌ **Don't use Expressway mode when:**
- You're inside the corporate network
- You can access CUCM directly
- DNS `_cisco-uds._tcp` resolves to CUCM
- You want fastest performance (direct connection is faster)

## DNS Service Discovery

Jabber4Linux automatically detects if you're using Expressway or direct CUCM:

### Internal Network (Direct CUCM)
```bash
# DNS SRV query
_cisco-uds._tcp.example.com → cucm.example.com:8443
```

### External Network (Expressway)
```bash
# DNS SRV query
_collab-edge._tls.example.com → expressway-e.example.com:8443
```

**Auto-detection**: If `_collab-edge._tls` SRV record is found, Jabber4Linux automatically enables Expressway mode!

## Manual Configuration

### Login Window

When logging in, you'll see:

```
Server: [expressway-e.example.com]
Port: [8443]

Authentication:
○ Username/Password
● SAML SSO

☑ Using Expressway-C (external/MRA)

[Login with SAML]
```

**Checkbox explained:**
- ☑️ **Checked**: Connecting via Expressway (external/remote)
- ☐ **Unchecked**: Direct CUCM connection (internal network)

### Server Address

**For Expressway:**
- Enter the **Expressway-E external FQDN**: `expressway-e.example.com`
- Port: Usually `8443` (or `443` depending on deployment)

**For Direct CUCM:**
- Enter the **CUCM FQDN**: `cucm.example.com`
- Port: `8443` (standard)

## SAML Authentication Flow with Expressway

```
1. User clicks "Login with SAML"
2. Jabber4Linux opens browser to:
   https://expressway-e.example.com:8443/ssosp/saml/login

3. Expressway-E proxies to Expressway-C

4. Expressway-C proxies to CUCM:
   https://cucm.example.com:8443/ssosp/saml/login

5. CUCM redirects to Keycloak:
   https://keycloak.example.com/auth/realms/.../protocol/saml

6. User authenticates with Keycloak

7. Keycloak sends SAML assertion back to CUCM (via Expressway)

8. CUCM creates session cookies

9. Cookies proxied back through Expressway-C → Expressway-E

10. Jabber4Linux receives cookies

11. All UDS API calls go through Expressway:
    https://expressway-e.example.com:8443/cucm-uds/...
```

## Certificate Configuration

### Expressway Certificates

Place Expressway certificates in:
```
~/.config/jabber4linux/server-certs/
```

**You need certificates for:**
1. **Expressway-E** (external facing)
2. **Expressway-C** (internal)
3. **CUCM** (backend)
4. **Keycloak** (IdP)

### Export Certificates

**From Expressway:**
```bash
# SSH to Expressway-E
ssh admin@expressway-e.example.com
utils tls certificate export

# Copy certificate.pem to:
~/.config/jabber4linux/server-certs/expressway-e.pem
```

**From CUCM:**
```
1. CUCM Admin → OS Administration
2. Security → Certificate Management
3. Download tomcat.pem
4. Copy to: ~/.config/jabber4linux/server-certs/cucm.pem
```

## Expressway Configuration Requirements

### On Expressway-C

**1. HTTP Proxy (CUCM) Configuration:**
```
Applications → Unified Communications → Configuration
HTTP Proxy: Enabled
HTTP server 1: cucm.example.com
```

**2. SAML Proxy:**
```
Path: /ssosp
Target: cucm.example.com
```

**3. UDS Proxy:**
```
Path: /cucm-uds
Target: cucm.example.com
```

### On Expressway-E

**1. Traversal Zone to Expressway-C:**
```
Peer address: expressway-c.example.com
```

**2. DNS Settings:**
```
DNS SRV record: _collab-edge._tls
Target: expressway-e.example.com
Port: 8443
```

## Testing Expressway Connection

### 1. Test DNS Discovery
```bash
# From external network
dig _collab-edge._tls.example.com SRV

# Should return:
# _collab-edge._tls.example.com. IN SRV 0 0 8443 expressway-e.example.com.
```

### 2. Test Expressway HTTPS
```bash
curl -v https://expressway-e.example.com:8443/
# Should get CUCM login page (proxied)
```

### 3. Test SAML Endpoint
```bash
curl -v https://expressway-e.example.com:8443/ssosp/saml/login
# Should redirect to Keycloak
```

### 4. Test UDS API
```bash
curl -k -u username:password \
  https://expressway-e.example.com:8443/cucm-uds/user/username
# Should return user details XML
```

## Troubleshooting

### Problem: "Connection refused" to Expressway

**Cause**: Expressway not reachable or wrong port

**Solution:**
1. Verify Expressway FQDN: `ping expressway-e.example.com`
2. Check port (usually 8443 or 443)
3. Verify firewall allows outbound HTTPS

### Problem: "SSL Certificate Error"

**Cause**: Expressway certificate not trusted

**Solution:**
1. Download Expressway-E certificate
2. Place in `~/.config/jabber4linux/server-certs/`
3. Restart Jabber4Linux

### Problem: "No CUCM session cookies found"

**Cause**: Expressway not proxying SAML correctly

**Solution:**
1. Verify Expressway HTTP proxy config
2. Check `/ssosp` path is proxied to CUCM
3. Test SAML login in browser manually
4. Enable debug mode: `python3 -m jabber4linux --debug`

### Problem: "Device not found" after SAML login

**Cause**: UDS API not reachable through Expressway

**Solution:**
1. Verify `/cucm-uds` path is proxied
2. Test: `curl https://expressway-e.example.com:8443/cucm-uds/version`
3. Check Expressway-C can reach CUCM

### Problem: "Session timeout" too quick

**Cause**: Expressway or CUCM session timeout settings

**Solution:**
1. Check CUCM SAML SSO session timeout
2. Check Expressway session timeout settings
3. May need to re-authenticate more frequently

## Performance Considerations

### Latency
- **Direct CUCM**: ~10-50ms (internal network)
- **Via Expressway**: ~100-500ms (depends on internet connection)

### Recommendation
- **Internal users**: Use direct CUCM connection (uncheck Expressway)
- **External users**: Use Expressway (check Expressway box)
- **Hybrid**: Auto-detection handles this based on DNS

## Security Best Practices

1. **Always use HTTPS** - Never HTTP for Expressway
2. **Validate certificates** - Don't disable certificate validation
3. **Use strong passwords** - Keycloak enforces this
4. **Enable MFA** - Configure in Keycloak
5. **Monitor sessions** - Check CUCM session logs

## Advanced: Split DNS

For organizations using split DNS (internal vs external):

### Internal DNS
```
cucm.example.com → 10.1.1.10 (internal IP)
_cisco-uds._tcp.example.com → cucm.example.com:8443
```

### External DNS
```
expressway-e.example.com → 203.0.113.10 (public IP)
_collab-edge._tls.example.com → expressway-e.example.com:8443
```

**Jabber4Linux behavior:**
- Internal network → Resolves CUCM → Direct connection
- External network → Resolves Expressway-E → MRA connection

## References

- [Cisco Expressway MRA Deployment Guide](https://www.cisco.com/c/en/us/support/unified-communications/expressway-series/products-installation-and-configuration-guides-list.html)
- [Mobile Remote Access with Expressway](https://www.cisco.com/c/en/us/td/docs/voice_ip_comm/expressway/config_guide/X14-0/exwy_b_mra-expressway-deployment-guide.html)
- [Jabber MRA Configuration](https://www.cisco.com/c/en/us/support/unified-communications/jabber-windows/products-installation-and-configuration-guides-list.html)

## Summary

✅ **Jabber4Linux with Expressway:**
- Auto-detects Expressway via DNS
- Manual checkbox for override
- Same SAML flow, proxied through Expressway
- Requires Expressway certificates
- Slightly higher latency than direct connection

✅ **Best Practice:**
- Let auto-detection handle it
- Only manually check Expressway box if auto-detection fails
- Use direct CUCM when on internal network for best performance
