# SAML Authentication Debugging Guide

This guide helps you troubleshoot SAML SSO authentication issues in Jabber4Linux.

## Quick Test Script

Run the automated test suite:

```bash
cd /home/user/jabber4linux
python3 test_saml_auth.py --server YOUR-CUCM-SERVER --interactive --debug
```

This will test:
1. Network connectivity
2. SAML endpoint availability
3. UDS API access
4. DNS discovery
5. Interactive SAML login (if --interactive)

## Common Problems and Solutions

### Problem 1: Application won't start without DNS

**Symptom:**
```
Exception: UDS server not found
```

**Solution:**
✅ **FIXED** - DNS is now optional. Manually enter server address in login window.

**Test:**
```bash
python3 -m jabber4linux --debug
# Should start even without DNS _cisco-uds._tcp records
```

---

### Problem 2: "No CUCM session cookies found"

**Symptom:**
- Browser opens for SAML login
- You log in successfully to Keycloak
- Window doesn't close
- No cookies appear in debug output

**Causes:**
1. Cookies not being set by CUCM
2. Cookie extraction timing issue
3. Wrong cookie domain
4. Browser security settings

**Debug Steps:**

**Step 1: Check SAML flow in browser**
```bash
# Run with debug mode
python3 -m jabber4linux --debug

# Watch console output for:
:: URL changed: https://keycloak.../auth/realms/...
:: Cookie received: JSESSIONID
:: Cookie received: JSESSIONIDSSO
```

**Step 2: Verify CUCM SAML configuration**
- Log into CUCM Admin
- Go to: User Management → User Settings → SAML Single Sign-On
- Verify: SAML SSO is Enabled
- Test SSO URL: https://YOUR-CUCM:8443/ssosp/saml/login

**Step 3: Check cookie timing**
The code now waits longer for cookies. If still not working:
- Increase timeout in `SamlAuthClient.py`:
  ```python
  QtCore.QTimer.singleShot(3000, self.check_authentication)  # Was 2000
  ```

**Step 4: Manual cookie test**
Open browser manually and check cookies:
```bash
# In browser DevTools (F12) → Application → Cookies
# After SAML login, check for:
- JSESSIONID (CUCM session)
- JSESSIONIDSSO (SAML SSO session)
```

---

### Problem 3: SSL Certificate Errors

**Symptom:**
```
SSL: CERTIFICATE_VERIFY_FAILED
```

**Solution:**

**Option A: Add trusted certificates (Recommended)**
```bash
mkdir -p ~/.config/jabber4linux/server-certs/

# Export CUCM certificate
# From CUCM: OS Administration → Security → Certificate Management
# Download tomcat.pem

cp tomcat.pem ~/.config/jabber4linux/server-certs/cucm.pem

# Also add Keycloak certificate if self-signed
openssl s_client -connect keycloak.example.com:443 -showcerts </dev/null 2>/dev/null | \
  openssl x509 -outform PEM > ~/.config/jabber4linux/server-certs/keycloak.pem
```

**Option B: Temporary - Disable verification (NOT FOR PRODUCTION)**
Edit `SamlAuthClient.py`:
```python
# In SamlWebPage.certificateError():
return True  # Already set - accepts self-signed certs
```

---

### Problem 4: SAML Redirect Loop

**Symptom:**
- Browser keeps redirecting between CUCM and Keycloak
- Never completes authentication

**Causes:**
1. SAML assertion validation failure
2. Clock synchronization issues
3. Wrong SAML attribute mapping

**Solutions:**

**Check 1: Clock Sync**
```bash
# On all servers (CUCM, Keycloak, client)
date
# Must be within 5 minutes of each other

# Sync time if needed
sudo ntpdate -u pool.ntp.org
```

**Check 2: SAML Attribute Mapping**
- In Keycloak → Clients → CUCM → Mappers
- Verify `uid` attribute is mapped
- Must match LDAP user ID in CUCM

**Check 3: CUCM SAML Logs**
```bash
# SSH to CUCM
admin:utils saml idp-metadata show
admin:show perf query class "Tomcat SAML SSO Counters"
```

---

### Problem 5: "Username Required" prompt appears

**Symptom:**
After SAML login, prompted for username

**Why:**
UDS API requires username to fetch device configuration. SAML assertion doesn't always contain it.

**Solutions:**

**Option A: Enter username manually (Current behavior)**
- Enter your LDAP username when prompted

**Option B: Auto-extract from SAML (Future enhancement)**
- Would need to parse SAML assertion response
- Extract `uid` or `nameid` attribute

**Workaround:**
Pre-fill username in login window before clicking "Login with SAML"

---

### Problem 6: Expressway Connection Issues

**Symptom:**
Using Expressway-C proxy, authentication fails

**Debug:**
```bash
# Test Expressway connectivity
curl -k https://expressway-e.example.com:8443/

# Test SAML through Expressway
curl -k -L https://expressway-e.example.com:8443/ssosp/saml/login
# Should redirect to Keycloak

# Test UDS through Expressway
curl -k https://expressway-e.example.com:8443/cucm-uds/version
```

**Solutions:**

**Check 1: Expressway HTTP Proxy Config**
- Expressway-C → Applications → Unified Communications → Configuration
- HTTP Proxy: Enabled
- HTTP server 1: cucm.example.com

**Check 2: Path Mappings**
```
/ssosp → cucm.example.com
/cucm-uds → cucm.example.com
```

**Check 3: Certificates**
Add both Expressway and CUCM certificates:
```bash
~/.config/jabber4linux/server-certs/expressway-e.pem
~/.config/jabber4linux/server-certs/expressway-c.pem
~/.config/jabber4linux/server-certs/cucm.pem
```

---

## Debug Mode Output Explained

When running with `--debug`, you'll see:

```bash
# DNS Discovery
:: CUCM direct discovery (_cisco-uds._tcp) failed: ...
:: Expressway discovery (_collab-edge._tls) failed: ...
# ^ Normal if using manual server entry

# Authentication Mode
:: UdsWrapper using SAML cookie-based authentication
# ^ Confirms SAML mode is active

# SAML Client
:: SAML client configured for Expressway-C proxy: expressway-e.example.com:8443
# ^ Shows detected mode (Expressway vs direct CUCM)

# Browser Navigation
:: URL changed: https://cucm.example.com:8443/ssosp/saml/login
:: URL changed: https://keycloak.example.com/auth/realms/master/protocol/saml
:: URL changed: https://cucm.example.com:8443/ssosp/...
# ^ Shows SAML redirect flow

# Cookie Collection
:: Cookie received: JSESSIONID
:: Cookie received: JSESSIONIDSSO
:: Found CUCM session cookie: JSESSIONID
:: Found CUCM session cookie: JSESSIONIDSSO
# ^ Successful cookie capture

# Authentication Complete
:: Checking authentication... Collected cookies: ['JSESSIONID', 'JSESSIONIDSSO', ...]
:: Found CUCM session cookies: ['JSESSIONID', 'JSESSIONIDSSO']
:: Authentication complete with 2 CUCM cookies
# ^ Success!
```

---

## Logging Detailed Flow

For maximum debugging, enable all logging:

**1. Python Debug Mode:**
```bash
export PYTHONVERBOSE=1
python3 -m jabber4linux --debug
```

**2. Qt Debug Output:**
```bash
export QT_LOGGING_RULES="qt.webenginecontext.debug=true"
python3 -m jabber4linux --debug
```

**3. Capture to File:**
```bash
python3 -m jabber4linux --debug 2>&1 | tee jabber4linux-debug.log
```

---

## Test SAML Flow Manually

### Step-by-Step Manual Test:

**1. Test SAML Endpoint:**
```bash
curl -k -v -L https://YOUR-CUCM:8443/ssosp/saml/login 2>&1 | grep -E "Location:|Set-Cookie:"
```

Expected output:
```
< Location: https://keycloak.example.com/auth/realms/...
```

**2. Complete SAML in Browser:**
- Open: https://YOUR-CUCM:8443/ssosp/saml/login
- Log in to Keycloak
- After redirect back to CUCM, open DevTools (F12)
- Check Application → Cookies → https://YOUR-CUCM:8443
- Should see: JSESSIONID, JSESSIONIDSSO

**3. Test UDS API with Cookie:**
```bash
# Copy cookie value from browser
curl -k -H "Cookie: JSESSIONID=YOUR-COOKIE-VALUE" \
  https://YOUR-CUCM:8443/cucm-uds/user/YOUR-USERNAME
```

Expected: XML with user details

---

## Network Trace

Capture network traffic:

```bash
# Install tcpdump
sudo apt install tcpdump

# Capture HTTPS traffic
sudo tcpdump -i any -s 0 -w saml-auth.pcap host YOUR-CUCM-IP or host YOUR-KEYCLOAK-IP

# Then run Jabber4Linux
python3 -m jabber4linux

# Analyze with Wireshark
wireshark saml-auth.pcap
```

Look for:
- TLS handshakes succeeding
- HTTP redirects (302)
- Set-Cookie headers

---

## Code Locations for Debugging

If you need to modify the code:

**Cookie Handling:**
- File: `jabber4linux/SamlAuthClient.py`
- Function: `on_cookie_added()` - Line ~168
- Function: `check_authentication()` - Line ~199
- Function: `complete_authentication()` - Line ~268

**Server Connection:**
- File: `jabber4linux/UdsWrapper.py`
- Function: `__init__()` - Line ~52 (SAML mode detection)
- Function: `get_auth_headers()` - Line ~133 (Cookie vs Basic Auth)

**Login UI:**
- File: `jabber4linux/Jabber4Linux.py`
- Function: `loginWithSaml()` - Line ~253
- Function: `completeSamlLogin()` - Line ~293

---

## Getting Help

If you're still stuck:

**1. Run test suite:**
```bash
cd /home/user/jabber4linux
python3 test_saml_auth.py --server YOUR-SERVER --interactive --debug > test-output.txt 2>&1
```

**2. Capture debug log:**
```bash
python3 -m jabber4linux --debug 2>&1 | tee debug.log
```

**3. Check these logs:**
- Client debug log (above)
- CUCM Tomcat logs: `/var/log/active/tomcat/logs/catalina.out`
- Keycloak logs: `/opt/keycloak/standalone/log/server.log`

**4. Provide information:**
- CUCM version
- Keycloak version
- Python version: `python3 --version`
- PyQt6 version: `pip show PyQt6 PyQt6-WebEngine`
- Test output
- Debug log
- Error messages

**5. Open issue:**
https://github.com/alun-hub/jabber4linux-saml/issues

---

## Quick Reference

**Start with debug:**
```bash
python3 -m jabber4linux --debug
```

**Run tests:**
```bash
python3 test_saml_auth.py --server YOUR-SERVER --interactive
```

**Check cookies manually:**
- Browser DevTools → Application → Cookies
- Look for: JSESSIONID, JSESSIONIDSSO

**Verify CUCM SAML:**
- CUCM Admin → SAML SSO → Test
- URL: https://YOUR-CUCM:8443/ssosp/saml/login

**Check certificates:**
```bash
ls -la ~/.config/jabber4linux/server-certs/
openssl x509 -in cucm.pem -text -noout
```

**Re-test DNS:**
```bash
dig _cisco-uds._tcp.YOUR-DOMAIN SRV
dig _collab-edge._tls.YOUR-DOMAIN SRV
```

---

## Success Checklist

Before reporting an issue, verify:

- [ ] CUCM is reachable: `ping YOUR-CUCM`
- [ ] HTTPS works: `curl -k https://YOUR-CUCM:8443/`
- [ ] SAML SSO enabled in CUCM
- [ ] Keycloak is configured as IdP
- [ ] SAML test works in browser
- [ ] Certificates added if self-signed
- [ ] Python 3.8+ installed
- [ ] PyQt6-WebEngine installed
- [ ] Test script passes: `python3 test_saml_auth.py --server YOUR-SERVER`

If all checked and still not working, it's a bug - please report it!
