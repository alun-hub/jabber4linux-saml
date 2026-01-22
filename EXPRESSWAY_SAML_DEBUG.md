# Expressway SAML Debug Guide - Primary Configuration

This guide is optimized for **Expressway-C as the primary deployment**, which is the recommended Cisco architecture for SAML SSO with Jabber.

## Why Expressway First?

**Modern Cisco Deployments:**
- ✅ Expressway is the standard for Mobile Remote Access (MRA)
- ✅ Works from anywhere (office, home, mobile)
- ✅ Better security with DMZ architecture
- ✅ Single configuration for all locations
- ✅ Required for mobile devices

**Direct CUCM:**
- Only works on internal network
- Not accessible remotely
- Requires VPN for external access
- Less flexible

## Architecture Overview

```
You → Internet → Expressway-E → Expressway-C → CUCM → Keycloak
              (DMZ/External)  (Internal DMZ)  (Internal)
```

**All traffic goes through Expressway** - SAML, UDS API, SIP, everything.

## Quick Start - Expressway Configuration

### Step 1: Verify Expressway is Reachable

```bash
# Test Expressway-E connectivity
curl -k https://YOUR-EXPRESSWAY-E:8443/

# Expected: CUCM login page (proxied through Expressway)
```

### Step 2: Test SAML Endpoint

```bash
# SAML login through Expressway
curl -k -L https://YOUR-EXPRESSWAY-E:8443/ssosp/saml/login

# Expected: Redirect to Keycloak
# Location: https://keycloak.../auth/realms/...
```

### Step 3: Run Automated Test

```bash
cd /home/user/jabber4linux
python3 test_saml_auth.py --server YOUR-EXPRESSWAY-E --port 8443 --interactive --debug
```

**What the test checks:**
1. ✓ Expressway connectivity
2. ✓ SAML proxy working
3. ✓ UDS API proxy working
4. ✓ DNS (optional)
5. ✓ Full SAML login flow

### Step 4: Start Jabber4Linux

```bash
python3 -m jabber4linux --debug
```

**Login Configuration:**
```
Server: YOUR-EXPRESSWAY-E
Port: 8443
☑ Using Expressway-C (external/MRA)  ← CHECK THIS BOX
Authentication: SAML SSO
```

## DNS Configuration (Recommended)

**For automatic Expressway detection:**

```dns
; Priority 0 = Expressway (preferred)
_collab-edge._tls.YOUR-DOMAIN. IN SRV 0 0 8443 expressway-e.YOUR-DOMAIN.

; Priority 10 = Direct CUCM (fallback, internal only)
_cisco-uds._tcp.YOUR-DOMAIN. IN SRV 10 0 8443 cucm.YOUR-DOMAIN.
```

**Test DNS:**
```bash
dig _collab-edge._tls.YOUR-DOMAIN SRV
# Should return: expressway-e.YOUR-DOMAIN:8443
```

**Jabber4Linux will automatically:**
1. Try `_collab-edge._tls` first (Expressway)
2. Fallback to `_cisco-uds._tcp` (direct CUCM)
3. Auto-check "Using Expressway-C" box if found

## Common Expressway Issues

### Issue 1: "Connection refused" to Expressway

**Debug:**
```bash
# Test basic connectivity
ping YOUR-EXPRESSWAY-E

# Test HTTPS
curl -k https://YOUR-EXPRESSWAY-E:8443/
```

**Solutions:**
- ✓ Verify firewall allows TCP 8443 outbound
- ✓ Check Expressway-E is online
- ✓ Verify DNS resolves correctly
- ✓ Try port 443 instead of 8443

### Issue 2: "SAML endpoint not found"

**Debug:**
```bash
curl -k -v https://YOUR-EXPRESSWAY-E:8443/ssosp/saml/login 2>&1 | grep -E "HTTP/|Location:"
```

**Expected output:**
```
< HTTP/1.1 302 Found
< Location: https://keycloak.../auth/realms/.../protocol/saml
```

**Solutions:**

**A. Check Expressway-C HTTP Proxy:**
```
Expressway-C Admin → Applications → Unified Communications → HTTP Proxy

Verify:
- HTTP Proxy: Enabled
- HTTP server 1: YOUR-CUCM-ADDRESS
- Paths mapped:
  /ssosp → cucm.YOUR-DOMAIN
  /cucm-uds → cucm.YOUR-DOMAIN
```

**B. Check Expressway-C to CUCM connectivity:**
```bash
# SSH to Expressway-C
ssh admin@expressway-c.YOUR-DOMAIN

# Test CUCM reachability
utils network ping YOUR-CUCM
utils network test YOUR-CUCM 8443
```

### Issue 3: "No CUCM session cookies"

**This is the most common Expressway SAML issue!**

**Debug Steps:**

**Step 1: Verify SAML works in browser manually**
```bash
# Open in browser (Chrome/Firefox)
https://YOUR-EXPRESSWAY-E:8443/ssosp/saml/login

# Log in with Keycloak
# After redirect back, open DevTools (F12)
# Application → Cookies → https://YOUR-EXPRESSWAY-E:8443
# Should see: JSESSIONID, JSESSIONIDSSO
```

**Step 2: Check cookie domain**

Cookies must be set for Expressway domain, not CUCM domain.

**Problem:**
```
Cookie domain: .cucm.YOUR-DOMAIN  ← WRONG for Expressway
```

**Solution:**
```
Cookie domain: .expressway-e.YOUR-DOMAIN  ← CORRECT
```

**Fix in CUCM:**
```
CUCM Admin → System → SAML Single Sign-On
Entity ID: Use Expressway FQDN (not CUCM FQDN)
```

**Step 3: Check Expressway proxy cookie handling**

```
Expressway-C → Applications → HTTP Proxy → Advanced

Verify:
- Cookie passthrough: Enabled
- Session stickiness: Enabled
```

### Issue 4: SSL Certificate Errors

**With Expressway, you need multiple certificates:**

```bash
mkdir -p ~/.config/jabber4linux/server-certs/

# 1. Expressway-E certificate (external facing)
# 2. Expressway-C certificate (internal)
# 3. CUCM certificate (backend)
# 4. Keycloak certificate (IdP)
```

**Export Expressway-E cert:**
```bash
# Method 1: Browser
# Open: https://YOUR-EXPRESSWAY-E:8443
# Click padlock → Certificate → Export

# Method 2: OpenSSL
openssl s_client -connect YOUR-EXPRESSWAY-E:8443 -showcerts </dev/null 2>/dev/null | \
  openssl x509 -outform PEM > ~/.config/jabber4linux/server-certs/expressway-e.pem
```

**Verify certificate:**
```bash
openssl x509 -in ~/.config/jabber4linux/server-certs/expressway-e.pem -text -noout | grep -E "Subject:|Issuer:|DNS:"
```

### Issue 5: SAML works in browser but not in Jabber4Linux

**Cause:** Cookie domain or path mismatch

**Debug:**
```bash
# Run with maximum debug
export QT_LOGGING_RULES="qt.webenginecontext.debug=true"
python3 -m jabber4linux --debug 2>&1 | tee debug.log

# Watch for:
:: Cookie received: JSESSIONID
:: Found CUCM session cookie: JSESSIONID
```

**If no cookies appear:**

1. **Check cookie path**
   - Cookies must be for path `/` or `/cucm-uds`
   - Not `/ssosp` only

2. **Check cookie SameSite attribute**
   - Should be: `SameSite=None` or `SameSite=Lax`
   - Not: `SameSite=Strict`

3. **Increase cookie wait time**
   - Edit `SamlAuthClient.py`
   - Line ~187: Change `QtCore.QTimer.singleShot(2000, ...)` to `3000` or `4000`

## Expressway-Specific Debug Output

**Successful Expressway SAML login looks like:**

```bash
python3 -m jabber4linux --debug

:: Found Expressway via DNS: expressway-e.YOUR-DOMAIN:8443
:: SAML client configured for Expressway-C proxy: expressway-e.YOUR-DOMAIN:8443
:: UdsWrapper using SAML cookie-based authentication
:: Loading SAML login URL: https://expressway-e.YOUR-DOMAIN:8443/ssosp/saml/login

:: URL changed: https://expressway-e.YOUR-DOMAIN:8443/ssosp/saml/login
:: URL changed: https://keycloak.YOUR-DOMAIN/auth/realms/YOUR-REALM/protocol/saml
:: Page load finished: True, URL: https://keycloak.YOUR-DOMAIN/auth/realms/.../login
[User logs in to Keycloak]
:: URL changed: https://keycloak.YOUR-DOMAIN/auth/realms/.../saml
:: URL changed: https://expressway-e.YOUR-DOMAIN:8443/ssosp/saml/authenticate
:: Detected CUCM redirect - checking authentication

:: Cookie received: JSESSIONID
:: Found CUCM session cookie: JSESSIONID
:: Cookie received: JSESSIONIDSSO
:: Found CUCM session cookie: JSESSIONIDSSO

:: Checking authentication... Collected cookies: ['JSESSIONID', 'JSESSIONIDSSO', ...]
:: Found CUCM session cookies: ['JSESSIONID', 'JSESSIONIDSSO']
:: Authentication complete with 2 CUCM cookies
✓ Authentication successful!

:: UdsWrapper using SAML cookie-based authentication
[Making UDS API calls through Expressway...]
```

## Expressway Configuration Checklist

Before troubleshooting, verify:

### Expressway-E (External)
- [ ] Reachable from internet on TCP 8443
- [ ] Valid SSL certificate (not expired)
- [ ] Traversal zone to Expressway-C configured
- [ ] DNS record: `_collab-edge._tls` points to Expressway-E

### Expressway-C (Internal)
- [ ] HTTP Proxy enabled
- [ ] CUCM configured as HTTP server
- [ ] Paths mapped: `/ssosp`, `/cucm-uds`
- [ ] Can reach CUCM on TCP 8443
- [ ] Cookie passthrough enabled

### CUCM
- [ ] SAML SSO enabled
- [ ] Keycloak configured as IdP
- [ ] Entity ID uses Expressway FQDN (not CUCM FQDN)
- [ ] Session timeout: 20+ minutes
- [ ] UDS service running

### Keycloak
- [ ] SAML client created for CUCM
- [ ] Valid redirect URIs include: `https://YOUR-EXPRESSWAY-E:8443/*`
- [ ] `uid` attribute mapped
- [ ] Client signature required: OFF (or properly configured)

## Testing Expressway SAML Flow

### Manual Test Procedure

**Step 1: Test Expressway Proxy**
```bash
curl -k https://YOUR-EXPRESSWAY-E:8443/
# Should return CUCM login page HTML
```

**Step 2: Test SAML Redirect**
```bash
curl -k -L https://YOUR-EXPRESSWAY-E:8443/ssosp/saml/login 2>&1 | grep -i location
# Should redirect to Keycloak
```

**Step 3: Test UDS API**
```bash
# After getting SAML cookies from browser:
curl -k -H "Cookie: JSESSIONID=YOUR-COOKIE" \
  https://YOUR-EXPRESSWAY-E:8443/cucm-uds/user/YOUR-USERNAME

# Should return XML user details
```

**Step 4: Test with Jabber4Linux**
```bash
python3 test_saml_auth.py --server YOUR-EXPRESSWAY-E --interactive --debug
```

## Performance Tuning for Expressway

**Expected Latencies:**

| Operation | Time |
|-----------|------|
| DNS lookup | 50-200ms |
| Expressway-E → Expressway-C | 20-100ms |
| Expressway-C → CUCM | 10-50ms |
| CUCM → Keycloak | 50-200ms |
| **Total SAML login** | **500-2000ms** |

**Optimization Tips:**

1. **Use persistent cookies** (configured in CUCM SAML settings)
2. **Enable HTTP/2** on Expressway (if supported)
3. **Increase session timeout** to reduce re-authentication
4. **Use DNS caching** on client

## Logs to Check

### Jabber4Linux Debug Log
```bash
python3 -m jabber4linux --debug 2>&1 | tee jabber-debug.log
grep -E "Expressway|Cookie|SAML|Authentication" jabber-debug.log
```

### Expressway-E Logs
```bash
ssh admin@expressway-e.YOUR-DOMAIN
utils developer logs tail tomcat
# Watch for HTTP proxy requests
```

### Expressway-C Logs
```bash
ssh admin@expressway-c.YOUR-DOMAIN
utils developer logs tail tomcat
# Watch for CUCM connection attempts
```

### CUCM SAML Logs
```bash
# SSH to CUCM
ssh admin@cucm.YOUR-DOMAIN

# Tomcat logs
file tail activelog tomcat/logs/catalina.out

# Look for:
- SAML assertion received
- Session cookie created
- UDS API requests
```

## Quick Fixes

### Fix 1: Expressway Cookie Domain

**Problem:** Cookies set for CUCM, not Expressway

**Solution:**
```
CUCM → System → SAML SSO → Entity ID
Change: https://cucm.YOUR-DOMAIN:8443
To: https://expressway-e.YOUR-DOMAIN:8443
```

### Fix 2: Expressway Path Mapping

**Problem:** `/ssosp` or `/cucm-uds` not proxied

**Solution:**
```
Expressway-C → Applications → HTTP Proxy → Paths

Add:
Path: /ssosp
Target: cucm.YOUR-DOMAIN

Path: /cucm-uds
Target: cucm.YOUR-DOMAIN
```

### Fix 3: Expressway Traversal Zone

**Problem:** Expressway-E can't reach Expressway-C

**Solution:**
```
Expressway-E → Configuration → Zones → Traversal Client

Peer: expressway-c.YOUR-DOMAIN
Authentication: (configured)
Status: Active (green)
```

## Summary

**For Expressway deployments:**
1. ✅ DNS should resolve to Expressway-E (not CUCM)
2. ✅ All traffic goes through Expressway (SAML, UDS, SIP)
3. ✅ Check "Using Expressway-C" in Jabber4Linux
4. ✅ Verify HTTP proxy paths on Expressway-C
5. ✅ Ensure cookies are set for Expressway domain
6. ✅ Add all certificates (Expressway-E, C, CUCM, Keycloak)

**Most common issue:** Cookie domain mismatch - cookies set for CUCM instead of Expressway.

**Quick test:** Does SAML login work in a regular browser? If yes, but not in Jabber4Linux, it's a cookie extraction timing issue (increase wait times in code).

## Need More Help?

Run the comprehensive test:
```bash
python3 test_saml_auth.py --server YOUR-EXPRESSWAY-E --interactive --debug > test.log 2>&1
```

Then check:
- Can you connect? (Test 1)
- Does SAML redirect work? (Test 2)
- Is UDS API accessible? (Test 3)
- Does interactive login show cookies? (Test 5)

If Test 5 shows cookies in console but Jabber4Linux still doesn't work, you have a cookie extraction timing issue - see Fix 3 in "Issue 5" above.
